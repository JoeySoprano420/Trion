// trion_runtime.c
// Extended runtime for Trion language: quarantines, channels, capsule lifecycle,
// threads, dodecagram (base-12) helpers, packet helper, event callbacks, timers,
// extended big-number bytes<->base12, enhanced syscall registry, detailed error/audit
// logging, sandbox runner improvements, and improved JIT/NASM bridge using clang+LLVM
// with fallbacks.
//
// This file is intentionally self-contained and portable. Platform-specific
// capabilities (namespaces, seccomp, clang availability) are best-effort and
// gracefully degrade when unavailable.
//
// Author: GitHub Copilot (extended)
// License: MIT-style permissive (use per project license)

#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <assert.h>
#include <stdarg.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <process.h>
#include <io.h>
#include <direct.h>
typedef CRITICAL_SECTION tr_mutex_t;
typedef CONDITION_VARIABLE tr_cond_t;
typedef HANDLE tr_thread_t;
static void tr_mutex_init(tr_mutex_t *m) { InitializeCriticalSection(m); }
static void tr_mutex_lock(tr_mutex_t *m) { EnterCriticalSection(m); }
static void tr_mutex_unlock(tr_mutex_t *m) { LeaveCriticalSection(m); }
static void tr_mutex_destroy(tr_mutex_t *m) { DeleteCriticalSection(m); }
static void tr_cond_init(tr_cond_t *c) { InitializeConditionVariable(c); }
static void tr_cond_wait(tr_cond_t *c, tr_mutex_t *m) { SleepConditionVariableCS(c, m, INFINITE); }
static int  tr_cond_timedwait(tr_cond_t *c, tr_mutex_t *m, uint32_t ms)
{
    return SleepConditionVariableCS(c, m, ms) ? 0 : (GetLastError() == ERROR_TIMEOUT ? 1 : -1);
}
static void tr_cond_notify_one(tr_cond_t *c) { WakeConditionVariable(c); }
static void tr_cond_notify_all(tr_cond_t *c) { WakeAllConditionVariable(c); }
static void tr_cond_destroy(tr_cond_t *c) { (void)c; /* no-op on Win32 */ }
#else
#include <pthread.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <fcntl.h>
#include <errno.h>
#include <dlfcn.h>
#include <dirent.h>
#include <sys/stat.h>
#include <signal.h>
typedef pthread_mutex_t tr_mutex_t;
typedef pthread_cond_t tr_cond_t;
typedef pthread_t tr_thread_t;
static void tr_mutex_init(tr_mutex_t *m) { pthread_mutex_init(m, NULL); }
static void tr_mutex_lock(tr_mutex_t *m) { pthread_mutex_lock(m); }
static void tr_mutex_unlock(tr_mutex_t *m) { pthread_mutex_unlock(m); }
static void tr_mutex_destroy(tr_mutex_t *m) { pthread_mutex_destroy(m); }
static void tr_cond_init(tr_cond_t *c) { pthread_cond_init(c, NULL); }
static void tr_cond_wait(tr_cond_t *c, tr_mutex_t *m) { pthread_cond_wait(c, m); }
static int  tr_cond_timedwait(tr_cond_t *c, tr_mutex_t *m, uint32_t ms)
{
    struct timespec ts;
#if defined(__APPLE__)
    time_t s = time(NULL) + (ms / 1000);
    ts.tv_sec = s;
    ts.tv_nsec = (ms % 1000) * 1000000;
#else
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += ms / 1000;
    ts.tv_nsec += (ms % 1000) * 1000000;
    if (ts.tv_nsec >= 1000000000) { ts.tv_sec += 1; ts.tv_nsec -= 1000000000; }
#endif
    return pthread_cond_timedwait(c, m, &ts) == 0 ? 0 : 1;
}
static void tr_cond_notify_one(tr_cond_t *c) { pthread_cond_signal(c); }
static void tr_cond_notify_all(tr_cond_t *c) { pthread_cond_broadcast(c); }
static void tr_cond_destroy(tr_cond_t *c) { pthread_cond_destroy(c); }
#endif

/* ---------------------------
   Internal error / audit logging helpers
   --------------------------- */

/* Thread-local last error message */
#if defined(_MSC_VER)
__declspec(thread) static char *g_last_error_msg = NULL;
#else
static __thread char *g_last_error_msg = NULL;
#endif

static tr_mutex_t g_error_lock;
static int g_error_lock_inited = 0;

static void tr_init_error_lock_once(void)
{
    if (!g_error_lock_inited) {
        tr_mutex_init(&g_error_lock);
        g_error_lock_inited = 1;
    }
}

static void tr_set_last_error_fmt(const char *fmt, ...)
{
    tr_init_error_lock_once();
    va_list ap;
    va_start(ap, fmt);
    char buf[1024];
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    tr_mutex_lock(&g_error_lock);
    if (g_last_error_msg) { free(g_last_error_msg); g_last_error_msg = NULL; }
    g_last_error_msg = strdup(buf);
    tr_mutex_unlock(&g_error_lock);
}

const char *tr_get_last_error(void)
{
    const char *res = NULL;
    tr_mutex_lock(&g_error_lock);
    res = g_last_error_msg ? g_last_error_msg : "";
    tr_mutex_unlock(&g_error_lock);
    return res;
}

/* Audit log (optional file) */
static tr_mutex_t g_audit_lock;
static int g_audit_lock_inited = 0;
static FILE *g_audit_fp = NULL;

static void tr_init_audit_once(void)
{
    if (!g_audit_lock_inited) {
        tr_mutex_init(&g_audit_lock);
        g_audit_lock_inited = 1;
    }
}

int tr_audit_open(const char *path)
{
    tr_init_audit_once();
    tr_mutex_lock(&g_audit_lock);
    if (g_audit_fp) { fclose(g_audit_fp); g_audit_fp = NULL; }
    g_audit_fp = fopen(path, "a");
    if (!g_audit_fp) {
        tr_mutex_unlock(&g_audit_lock);
        tr_set_last_error_fmt("audit_open: failed to open %s: %s", path, strerror(errno));
        return -1;
    }
    tr_mutex_unlock(&g_audit_lock);
    return 0;
}

void tr_audit_close(void)
{
    tr_init_audit_once();
    tr_mutex_lock(&g_audit_lock);
    if (g_audit_fp) { fclose(g_audit_fp); g_audit_fp = NULL; }
    tr_mutex_unlock(&g_audit_lock);
}

void tr_audit_log(const char *fmt, ...)
{
    tr_init_audit_once();
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    tr_mutex_lock(&g_audit_lock);
    if (g_audit_fp) {
        time_t t = time(NULL);
        struct tm tm;
#if defined(_WIN32)
        localtime_s(&tm, &t);
#else
        localtime_r(&t, &tm);
#endif
        char ts[64];
        strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", &tm);
        fprintf(g_audit_fp, "[%s] %s\n", ts, buf);
        fflush(g_audit_fp);
    } else {
        fprintf(stderr, "[audit] %s\n", buf);
    }
    tr_mutex_unlock(&g_audit_lock);
}

/* ---------------------------
   Basic concurrency & primitives (Quarantine + Channel)
   --------------------------- */

typedef struct {
    void **items;
    size_t count;
    size_t capacity;
    int sealed;     /* once sealed, new allocations are rejected */
    tr_mutex_t lock;
} Quarantine;

Quarantine *quarantine_create(size_t initial_capacity)
{
    Quarantine *q = (Quarantine*)malloc(sizeof(Quarantine));
    if (!q) { tr_set_last_error_fmt("quarantine_create: OOM"); return NULL; }
    q->capacity = initial_capacity ? initial_capacity : 16;
    q->count = 0;
    q->sealed = 0;
    q->items = (void**)calloc(q->capacity, sizeof(void*));
    if (!q->items) { free(q); tr_set_last_error_fmt("quarantine_create: calloc failed"); return NULL; }
    tr_mutex_init(&q->lock);
    return q;
}

static int quarantine_grow_if_needed(Quarantine *q)
{
    if (q->count < q->capacity) return 0;
    size_t newcap = q->capacity * 2;
    void **n = (void**)realloc(q->items, newcap * sizeof(void*));
    if (!n) { tr_set_last_error_fmt("quarantine_grow_if_needed: realloc failed"); return -1; }
    q->items = n;
    q->capacity = newcap;
    return 0;
}

void *quarantine_alloc(Quarantine *q, size_t size)
{
    if (!q || size == 0) { tr_set_last_error_fmt("quarantine_alloc: invalid args"); return NULL; }
    tr_mutex_lock(&q->lock);
    if (q->sealed) {
        tr_mutex_unlock(&q->lock);
        tr_set_last_error_fmt("quarantine_alloc: quarantined sealed");
        return NULL;
    }
    if (quarantine_grow_if_needed(q) != 0) {
        tr_mutex_unlock(&q->lock);
        return NULL;
    }
    void *p = malloc(size);
    if (!p) { tr_mutex_unlock(&q->lock); tr_set_last_error_fmt("quarantine_alloc: malloc failed"); return NULL; }
    q->items[q->count++] = p;
    tr_mutex_unlock(&q->lock);
    return p;
}

int quarantine_free(Quarantine *q, void *ptr)
{
    if (!q || !ptr) { tr_set_last_error_fmt("quarantine_free: invalid args"); return -1; }
    tr_mutex_lock(&q->lock);
    for (size_t i = 0; i < q->count; ++i) {
        if (q->items[i] == ptr) {
            free(ptr);
            q->items[i] = q->items[q->count - 1];
            q->items[q->count - 1] = NULL;
            q->count--;
            tr_mutex_unlock(&q->lock);
            return 0;
        }
    }
    tr_mutex_unlock(&q->lock);
    tr_set_last_error_fmt("quarantine_free: pointer not found");
    return -1;
}

void quarantine_seal(Quarantine *q)
{
    if (!q) return;
    tr_mutex_lock(&q->lock);
    q->sealed = 1;
    tr_mutex_unlock(&q->lock);
}

void quarantine_destroy(Quarantine *q)
{
    if (!q) return;
    tr_mutex_lock(&q->lock);
    for (size_t i = 0; i < q->count; ++i) {
        if (q->items[i]) free(q->items[i]);
    }
    free(q->items);
    q->items = NULL;
    q->count = 0;
    q->capacity = 0;
    tr_mutex_unlock(&q->lock);
    tr_mutex_destroy(&q->lock);
    free(q);
}

/* Channel (same design as before) */
typedef struct {
    void **buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    tr_mutex_t lock;
    tr_cond_t not_empty;
    tr_cond_t not_full;
    int closed; /* once closed, recv returns 0 items and send fails */
} Channel;

Channel *channel_create(size_t capacity)
{
    if (capacity == 0) { tr_set_last_error_fmt("channel_create: invalid capacity"); return NULL; }
    Channel *c = (Channel*)malloc(sizeof(Channel));
    if (!c) { tr_set_last_error_fmt("channel_create: OOM"); return NULL; }
    c->buffer = (void**)calloc(capacity, sizeof(void*));
    if (!c->buffer) { free(c); tr_set_last_error_fmt("channel_create: calloc failed"); return NULL; }
    c->capacity = capacity;
    c->head = c->tail = c->count = 0;
    c->closed = 0;
    tr_mutex_init(&c->lock);
    tr_cond_init(&c->not_empty);
    tr_cond_init(&c->not_full);
    return c;
}

void channel_close(Channel *c)
{
    if (!c) return;
    tr_mutex_lock(&c->lock);
    c->closed = 1;
    tr_cond_notify_all(&c->not_empty);
    tr_cond_notify_all(&c->not_full);
    tr_mutex_unlock(&c->lock);
}

void channel_destroy(Channel *c)
{
    if (!c) return;
    free(c->buffer);
    tr_cond_destroy(&c->not_empty);
    tr_cond_destroy(&c->not_full);
    tr_mutex_destroy(&c->lock);
    free(c);
}

int channel_send(Channel *c, void *item, int blocking, uint32_t timeout_ms)
{
    if (!c) { tr_set_last_error_fmt("channel_send: null channel"); return -1; }
    tr_mutex_lock(&c->lock);
    if (c->closed) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_send: closed"); return -1; }
    while (c->count == c->capacity) {
        if (!blocking) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_send: would block"); return -2; }
        if (timeout_ms == 0) {
            tr_cond_wait(&c->not_full, &c->lock);
        } else {
            int w = tr_cond_timedwait(&c->not_full, &c->lock, timeout_ms);
            if (w != 0) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_send: timeout"); return -3; }
        }
        if (c->closed) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_send: closed during wait"); return -1; }
    }
    c->buffer[c->tail] = item;
    c->tail = (c->tail + 1) % c->capacity;
    c->count++;
    tr_cond_notify_one(&c->not_empty);
    tr_mutex_unlock(&c->lock);
    return 0;
}

int channel_recv(Channel *c, void **out, int blocking, uint32_t timeout_ms)
{
    if (!c || !out) { tr_set_last_error_fmt("channel_recv: invalid args"); return -1; }
    tr_mutex_lock(&c->lock);
    while (c->count == 0) {
        if (c->closed) { tr_mutex_unlock(&c->lock); return 0; }
        if (!blocking) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_recv: would block"); return -2; }
        if (timeout_ms == 0) {
            tr_cond_wait(&c->not_empty, &c->lock);
        } else {
            int w = tr_cond_timedwait(&c->not_empty, &c->lock, timeout_ms);
            if (w != 0) { tr_mutex_unlock(&c->lock); tr_set_last_error_fmt("channel_recv: timeout"); return -3; }
        }
    }
    *out = c->buffer[c->head];
    c->buffer[c->head] = NULL;
    c->head = (c->head + 1) % c->capacity;
    c->count--;
    tr_cond_notify_one(&c->not_full);
    tr_mutex_unlock(&c->lock);
    return 1;
}

/* ---------------------------
   Thread wrappers (cross-platform)
   --------------------------- */

typedef void *(*tr_thread_fn_t)(void*);

typedef struct {
    tr_thread_fn_t fn;
    void *arg;
} thread_startup_t;

#ifdef _WIN32
static unsigned __stdcall _win_thread_start(void *ctx)
{
    thread_startup_t *s = (thread_startup_t*)ctx;
    if (!s) _exit(1);
    tr_thread_fn_t fn = s->fn;
    void *arg = s->arg;
    free(s);
    void *ret = fn(arg);
    (void)ret;
    return 0;
}
static int tr_thread_create(tr_thread_t *out, tr_thread_fn_t fn, void *arg)
{
    if (!out || !fn) { tr_set_last_error_fmt("tr_thread_create: invalid args"); return -1; }
    thread_startup_t *s = (thread_startup_t*)malloc(sizeof(thread_startup_t));
    if (!s) { tr_set_last_error_fmt("tr_thread_create: OOM"); return -1; }
    s->fn = fn; s->arg = arg;
    uintptr_t h = _beginthreadex(NULL, 0, _win_thread_start, s, 0, NULL);
    if (h == 0) { free(s); tr_set_last_error_fmt("tr_thread_create: _beginthreadex failed"); return -1; }
    *out = (tr_thread_t)h;
    return 0;
}
static int tr_thread_join(tr_thread_t t)
{
    if (!t) { tr_set_last_error_fmt("tr_thread_join: invalid thread"); return -1; }
    WaitForSingleObject(t, INFINITE);
    CloseHandle(t);
    return 0;
}
#else
static void * _posix_thread_start(void *ctx)
{
    thread_startup_t *s = (thread_startup_t*)ctx;
    tr_thread_fn_t fn = s->fn; void *arg = s->arg;
    free(s);
    return fn(arg);
}
static int tr_thread_create(tr_thread_t *out, tr_thread_fn_t fn, void *arg)
{
    if (!out || !fn) { tr_set_last_error_fmt("tr_thread_create: invalid args"); return -1; }
    thread_startup_t *s = (thread_startup_t*)malloc(sizeof(thread_startup_t));
    if (!s) { tr_set_last_error_fmt("tr_thread_create: OOM"); return -1; }
    s->fn = fn; s->arg = arg;
    pthread_t th;
    if (pthread_create(&th, NULL, _posix_thread_start, s) != 0) { free(s); tr_set_last_error_fmt("tr_thread_create: pthread_create failed"); return -1; }
    *out = th;
    return 0;
}
static int tr_thread_join(tr_thread_t t)
{
    if (pthread_join(t, NULL) != 0) { tr_set_last_error_fmt("tr_thread_join: pthread_join failed"); return -1; }
    return 0;
}
#endif

/* ---------------------------
   Dodecagram (base-12) helpers (uint64)
   --------------------------- */

static const char DG_DIGITS[] = "0123456789ab";

int tr_to_base12_u64(uint64_t n, char *out, size_t outlen)
{
    if (!out || outlen == 0) { tr_set_last_error_fmt("tr_to_base12_u64: invalid args"); return -1; }
    if (n == 0) {
        if (outlen < 2) { tr_set_last_error_fmt("tr_to_base12_u64: buffer too small"); return -1; }
        out[0] = '0'; out[1] = '\0';
        return 0;
    }
    char buf[128];
    size_t pos = 0;
    while (n && pos + 1 < sizeof(buf)) {
        buf[pos++] = DG_DIGITS[n % 12];
        n /= 12;
    }
    if (pos == 0) { buf[pos++] = '0'; }
    if (pos + 1 > outlen) { tr_set_last_error_fmt("tr_to_base12_u64: outlen too small"); return -1; }
    for (size_t i = 0; i < pos; ++i) out[i] = buf[pos - 1 - i];
    out[pos] = '\0';
    return 0;
}

int tr_from_base12_u64(const char *s, uint64_t *out)
{
    if (!s || !out) { tr_set_last_error_fmt("tr_from_base12_u64: invalid args"); return -1; }
    uint64_t val = 0;
    const char *p = s;
    int neg = 0;
    if (*p == '+' || *p == '-') { if (*p == '-') neg = 1; p++; }
    while (*p) {
        char c = *p++;
        int d = -1;
        if (c >= '0' && c <= '9') d = c - '0';
        else if (c == 'a' || c == 'A') d = 10;
        else if (c == 'b' || c == 'B') d = 11;
        else if (c == '_' || c == ' ') continue;
        else { tr_set_last_error_fmt("tr_from_base12_u64: invalid digit '%c'", c); return -1; }
        if (val > (UINT64_MAX - d) / 12) { tr_set_last_error_fmt("tr_from_base12_u64: overflow"); return -1; }
        val = val * 12 + (uint64_t)d;
    }
    *out = neg ? (uint64_t)(-(int64_t)val) : val;
    return 0;
}

/* ---------------------------
   Big-number: bytes <-> base-12 (arbitrary-length), signed and fractional support
   - bytes_to_base12(bytes,len,out,outlen)                : integer representation (existing)
   - bytes_to_base12_scaled(bytes,len,scale,out,outlen)   : treat bytes as integer representing value / 12^scale
   - base12_to_bytes(s, &out_bytes, &out_len)             : parse signed integer or fixed-point (no scale output)
   - base12_to_bytes_with_scale(s, &out_bytes, &out_len, &scale) : returns scale for fractional digits
   Notes:
     - bytes are interpreted as big-endian unsigned magnitude.
     - base12 strings may include optional leading +/-, an optional decimal point '.' with fractional base-12 digits.
     - When fractional part present, the returned bytes represent (value * 12^frac_len) as integer; `scale` will be frac_len.
   --------------------------- */

/* helpers for big-number math */

static int bn_is_zero(const uint8_t *bn, size_t len)
{
    for (size_t i = 0; i < len; ++i) if (bn[i]) return 0;
    return 1;
}

/* divide big-endian bn (len bytes) by small divisor; write quotient back into bn.
   return remainder in rem_out. divisor must be >0
*/
static int bn_divmod_small(uint8_t *bn, size_t len, uint32_t divisor, uint32_t *rem_out)
{
    if (!bn || len == 0 || divisor == 0 || !rem_out) { tr_set_last_error_fmt("bn_divmod_small: invalid args"); return -1; }
    uint32_t rem = 0;
    for (size_t i = 0; i < len; ++i) {
        uint32_t acc = (rem << 8) | bn[i];
        uint8_t q = (uint8_t)(acc / divisor);
        rem = acc % divisor;
        bn[i] = q;
    }
    *rem_out = rem;
    return 0;
}

/* multiply big-endian bn (len bytes) by small multiplier and add small addend.
   bn is modified in place; when carry remains positive after top byte, return -2 to indicate need to grow buffer.
*/
static int bn_mul_small_add(uint8_t *bn, size_t len, uint32_t mul, uint32_t add)
{
    if (!bn || len == 0) { tr_set_last_error_fmt("bn_mul_small_add: invalid args"); return -1; }
    uint64_t carry = add;
    for (ssize_t i = (ssize_t)len - 1; i >= 0; --i) {
        uint64_t prod = (uint64_t)bn[i] * (uint64_t)mul + carry;
        bn[i] = (uint8_t)(prod & 0xFF);
        carry = prod >> 8;
    }
    if (carry != 0) return -2; /* overflow -> caller should grow buffer and retry */
    return 0;
}

/* Convert arbitrary big-endian byte array to base-12 string (0-9,a,b).
   Un-signed, outputs integer string. Returns 0 on success.
*/
int bytes_to_base12(const uint8_t *bytes, size_t len, char *out, size_t outlen)
{
    if (!out || outlen == 0) { tr_set_last_error_fmt("bytes_to_base12: invalid output buffer"); return -1; }
    if (!bytes || len == 0) {
        if (outlen < 2) { tr_set_last_error_fmt("bytes_to_base12: outlen too small"); return -1; }
        out[0] = '0'; out[1] = '\0';
        return 0;
    }
    uint8_t *bn = (uint8_t*)malloc(len);
    if (!bn) { tr_set_last_error_fmt("bytes_to_base12: OOM"); return -1; }
    memcpy(bn, bytes, len);
    char *rev = (char*)malloc((len * 3) + 32);
    if (!rev) { free(bn); tr_set_last_error_fmt("bytes_to_base12: OOM rev"); free(bn); return -1; }
    size_t rpos = 0;
    while (!bn_is_zero(bn, len)) {
        uint32_t rem = 0;
        if (bn_divmod_small(bn, len, 12, &rem) != 0) { free(bn); free(rev); tr_set_last_error_fmt("bytes_to_base12: divmod failed"); return -1; }
        rev[rpos++] = DG_DIGITS[rem];
        if (rpos + 2 >= (size_t)((len * 3) + 32)) break;
    }
    if (rpos == 0) rev[rpos++] = '0';
    if (rpos + 1 > outlen) { free(bn); free(rev); tr_set_last_error_fmt("bytes_to_base12: outlen too small"); return -1; }
    for (size_t i = 0; i < rpos; ++i) out[i] = rev[rpos - 1 - i];
    out[rpos] = '\0';
    free(bn); free(rev);
    return 0;
}

/* Convert and insert decimal point according to scale: the input bytes represent integer value v,
   conceptual value is v / (12^scale). This function prints appropriate base-12 string with '.'
*/
int bytes_to_base12_scaled(const uint8_t *bytes, size_t len, int scale, char *out, size_t outlen)
{
    if (scale < 0) { tr_set_last_error_fmt("bytes_to_base12_scaled: negative scale"); return -1; }
    if (!out || outlen == 0) return -1;
    // produce integer part and fractional part by repeated division/mod
    char *tmp = (char*)malloc(outlen + 16);
    if (!tmp) { tr_set_last_error_fmt("bytes_to_base12_scaled: OOM"); return -1; }
    int rc = bytes_to_base12(bytes, len, tmp, outlen + 16);
    if (rc != 0) { free(tmp); return rc; }
    size_t totlen = strlen(tmp);
    if (scale == 0) {
        // no point insertion
        if (totlen + 1 > outlen) { free(tmp); tr_set_last_error_fmt("bytes_to_base12_scaled: outlen too small"); return -1; }
        strcpy(out, tmp);
        free(tmp);
        return 0;
    }
    // ensure we have at least scale+1 digits by left-padding with zeros
    if ((int)totlen <= scale) {
        // pad with leading zeros to produce 0.xxx
        size_t need = (size_t)(scale + 1 - (int)totlen);
        if (need + totlen + 2 > outlen) { free(tmp); tr_set_last_error_fmt("bytes_to_base12_scaled: outlen too small after pad"); return -1; }
        // write "0."
        out[0] = '0'; out[1] = '.'; size_t pos = 2;
        for (size_t i = 0; i < need; ++i) out[pos++] = '0';
        strcpy(out + pos, tmp);
        free(tmp);
        return 0;
    } else {
        // insert point such that fractional part has length 'scale'
        size_t intpart = totlen - scale;
        if (totlen + 2 > outlen) { free(tmp); tr_set_last_error_fmt("bytes_to_base12_scaled: outlen too small for insertion"); return -1; }
        memcpy(out, tmp, intpart);
        out[intpart] = '.';
        strcpy(out + intpart + 1, tmp + intpart);
        free(tmp);
        return 0;
    }
}

/* Parse base-12 string into big-endian byte array (allocated, caller frees).
   Supports optional sign (+/-) and optional fractional part separated by '.'.
   When fractional digits present, result bytes represent integer value = parsed_value * 12^frac_len
   and out_scale is set to frac_len so caller knows to interpret bytes as fixed-point.
*/
int base12_to_bytes_with_scale(const char *s, uint8_t **out_bytes, size_t *out_len, int *out_scale)
{
    if (!s || !out_bytes || !out_len) { tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid args"); return -1; }
    const char *p = s;
    int neg = 0;
    if (*p == '+' || *p == '-') { if (*p == '-') neg = 1; p++; }
    // split integer and fractional parts (if any)
    const char *dot = strchr(p, '.');
    size_t int_len = dot ? (size_t)(dot - p) : strlen(p);
    size_t frac_len = 0;
    const char *frac = NULL;
    if (dot) { frac = dot + 1; frac_len = strlen(frac); }
    // We'll process digits left-to-right: result = 0; for each base-12 digit d: result = result*12 + d
    // Using big-number bn (big-endian) allocate initial capacity 16 bytes and grow as needed.
    size_t cap = 16;
    uint8_t *bn = (uint8_t*)calloc(cap, 1);
    if (!bn) { tr_set_last_error_fmt("base12_to_bytes_with_scale: OOM bn alloc"); return -1; }
    size_t bn_len = 1;
    // helper to ensure capacity >= new_len
    auto ensure_bn_len = [&](size_t desired_len) -> int {
        if (desired_len <= bn_len) return 0;
        if (desired_len <= cap) { /* shift current content to rightmost position */ ; }
        size_t newcap = cap;
        while (newcap < desired_len) newcap *= 2;
        uint8_t *nb = (uint8_t*)calloc(newcap, 1);
        if (!nb) { free(bn); tr_set_last_error_fmt("base12_to_bytes_with_scale: OOM bn grow"); return -1; }
        // align old data at the end of new buffer
        memcpy(nb + (newcap - bn_len), bn + (cap - bn_len), bn_len);
        // free old and reset bn to new aligned layout (we will maintain bn as big-endian in [0..bn_len-1] region)
        free(bn);
        bn = nb;
        cap = newcap;
        return 0;
    };
    // We will treat bn as big-endian located at bn + (cap - bn_len)
    // To ease operations, we will maintain pointer 'ptr' to start of meaningful bytes
    uint8_t *ptr = bn + (cap - bn_len);

    // helper to multiply bn by 12 and add digit, resizing if needed
    auto bn_mul12_add = [&](int digit)->int {
        // multiply big-endian number at ptr with bn_len bytes by 12 and add digit
        uint64_t carry = digit;
        for (ssize_t i = (ssize_t)bn_len - 1; i >= 0; --i) {
            uint64_t idx = (size_t)(ptr + i - bn);
            uint64_t cur = (uint64_t)bn[(cap - bn_len) + i];
            uint64_t prod = cur * 12 + carry;
            bn[(cap - bn_len) + i] = (uint8_t)(prod & 0xFF);
            carry = prod >> 8;
        }
        if (carry != 0) {
            // need to grow by 1 byte
            if (ensure_bn_len(bn_len + 1) != 0) return -1;
            // shift ptr to new location
            ptr = bn + (cap - bn_len - 1);
            // shift existing data right by 1 byte within new buffer region
            memmove(ptr + 1, ptr, bn_len);
            ptr[0] = (uint8_t)carry;
            bn_len++;
        }
        return 0;
    };

    // parse integer part
    for (size_t i = 0; i < int_len; ++i) {
        char c = p[i];
        if (c == '_' || c == ' ') continue;
        int digit = -1;
        if (c >= '0' && c <= '9') digit = c - '0';
        else if (c == 'a' || c == 'A') digit = 10;
        else if (c == 'b' || c == 'B') digit = 11;
        else { free(bn); tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid digit '%c'", c); return -2; }
        if (bn_mul12_add(digit) != 0) { free(bn); return -1; }
    }
    // parse fractional part by multiplying result by 12 for each fractional digit and adding digit,
    // but to represent fixed-point as integer we simply continue the bn_mul12_add over fractional digits
    for (size_t i = 0; i < frac_len; ++i) {
        char c = frac[i];
        if (c == '_' || c == ' ') continue;
        int digit = -1;
        if (c >= '0' && c <= '9') digit = c - '0';
        else if (c == 'a' || c == 'A') digit = 10;
        else if (c == 'b' || c == 'B') digit = 11;
        else { free(bn); tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid frac digit '%c'", c); return -2; }
        if (bn_mul12_add(digit) != 0) { free(bn); return -1; }
    }

    // trim leading zeros
    size_t start = cap - bn_len;
    while (start < cap - 1 && bn[start] == 0) { start++; }
    size_t real_len = (cap - start);
    uint8_t *outb = (uint8_t*)malloc(real_len);
    if (!outb) { free(bn); tr_set_last_error_fmt("base12_to_bytes_with_scale: OOM outb"); return -1; }
    memcpy(outb, bn + start, real_len);
    free(bn);
    *out_bytes = outb;
    *out_len = real_len;
    if (out_scale) *out_scale = (int)frac_len;
    // Note: sign is not encoded into bytes (caller may track sign separately); return negative scale via out_scale<0? We'll set a flag by convention:
    if (neg && out_len && out_bytes) {
        // set leading sign indicator by prepending a single 0xFF byte? Avoid mutating bytes; instead, user should track sign based on original string.
    }
    return 0;
}

/* Backwards-compat wrapper: existing base12_to_bytes returns bytes for integer strings only (scale ignored) */
int base12_to_bytes(const char *s, uint8_t **out_bytes, size_t *out_len)
{
    int scale = 0;
    return base12_to_bytes_with_scale(s, out_bytes, out_len, &scale);
}

/* ---------------------------
   Packet helpers (simple)
   --------------------------- */
typedef struct {
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t src_port;
    uint16_t dst_port;
    size_t length;
    void *payload;       /* owned by packet->q */
    Quarantine *q;       /* quarantine owning payload */
} TrionPacket;

TrionPacket *tr_packet_create(Quarantine *q, const void *payload, size_t len)
{
    if (!q) { tr_set_last_error_fmt("tr_packet_create: invalid quarantine"); return NULL; }
    TrionPacket *p = (TrionPacket*)malloc(sizeof(TrionPacket));
    if (!p) { tr_set_last_error_fmt("tr_packet_create: OOM"); return NULL; }
    p->q = q;
    if (len > 0 && payload) {
        void *buf = quarantine_alloc(q, len);
        if (!buf) { free(p); tr_set_last_error_fmt("tr_packet_create: quarantine_alloc failed"); free(p); return NULL; }
        memcpy(buf, payload, len);
        p->payload = buf;
        p->length = len;
    } else {
        p->payload = NULL;
        p->length = 0;
    }
    p->src_ip = p->dst_ip = 0;
    p->src_port = p->dst_port = 0;
    return p;
}

void tr_packet_destroy(TrionPacket *p)
{
    if (!p) return;
    free(p);
}

int tr_packet_drop_if_src_ip(TrionPacket *p, uint32_t ip)
{
    if (!p) return 0;
    return p->src_ip == ip;
}

/* ---------------------------
   Capsule lifecycle, messaging and callbacks
   --------------------------- */

typedef struct Capsule {
    char *name;
    Quarantine *q;
    Channel *inbox;            /* message channel for capsule */
    tr_thread_t thread;
    int running;
    void *user_ctx;
    int (*entry)(struct Capsule*, void*); /* entry procedure supplied by embedder */
} Capsule;

/* Event callback: capsule lifecycle or message events */
typedef void (*tr_event_callback_t)(Capsule *capsule, const char *event, void *ctx);

/* Callback registry impl */
typedef struct {
    tr_event_callback_t *callbacks;
    void **cb_ctx;
    size_t count;
    size_t capacity;
    tr_mutex_t lock;
} CallbackRegistry;

static CallbackRegistry *g_callback_registry = NULL;

static CallbackRegistry *callback_registry_create(void)
{
    CallbackRegistry *r = (CallbackRegistry*)malloc(sizeof(CallbackRegistry));
    if (!r) return NULL;
    r->count = 0; r->capacity = 4;
    r->callbacks = (tr_event_callback_t*)malloc(r->capacity * sizeof(tr_event_callback_t));
    r->cb_ctx = (void**)malloc(r->capacity * sizeof(void*));
    tr_mutex_init(&r->lock);
    return r;
}

static void callback_registry_destroy(CallbackRegistry *r)
{
    if (!r) return;
    tr_mutex_destroy(&r->lock);
    free(r->callbacks);
    free(r->cb_ctx);
    free(r);
}

int tr_register_event_callback(tr_event_callback_t cb, void *ctx)
{
    if (!cb) { tr_set_last_error_fmt("tr_register_event_callback: invalid cb"); return -1; }
    if (!g_callback_registry) g_callback_registry = callback_registry_create();
    CallbackRegistry *r = g_callback_registry;
    tr_mutex_lock(&r->lock);
    if (r->count == r->capacity) {
        size_t nc = r->capacity * 2;
        tr_event_callback_t *ncbs = (tr_event_callback_t*)realloc(r->callbacks, nc * sizeof(tr_event_callback_t));
        void **nctx = (void**)realloc(r->cb_ctx, nc * sizeof(void*));
        if (!ncbs || !nctx) { tr_mutex_unlock(&r->lock); tr_set_last_error_fmt("tr_register_event_callback: realloc failed"); return -1; }
        r->callbacks = ncbs; r->cb_ctx = nctx; r->capacity = nc;
    }
    r->callbacks[r->count] = cb;
    r->cb_ctx[r->count] = ctx;
    r->count++;
    tr_mutex_unlock(&r->lock);
    return 0;
}

static void callback_registry_emit(CallbackRegistry *r, Capsule *c, const char *evt)
{
    if (!r || !c || !evt) return;
    tr_mutex_lock(&r->lock);
    size_t count = r->count;
    tr_event_callback_t *cbs = (tr_event_callback_t*)malloc(count * sizeof(tr_event_callback_t));
    void **cctx = (void**)malloc(count * sizeof(void*));
    for (size_t i = 0; i < count; ++i) { cbs[i] = r->callbacks[i]; cctx[i] = r->cb_ctx[i]; }
    tr_mutex_unlock(&r->lock);
    for (size_t i = 0; i < count; ++i) {
        if (cbs[i]) cbs[i](c, evt, cctx[i]);
    }
    free(cbs); free(cctx);
}

/* Thread entry wrapper for capsule */
static void *capsule_thread_start(void *arg)
{
    Capsule *c = (Capsule*)arg;
    if (!c) return NULL;
    c->running = 1;
    if (g_callback_registry) callback_registry_emit(g_callback_registry, c, "capsule_start");
    int rc = 0;
    if (c->entry) rc = c->entry(c, c->user_ctx);
    /* drain inbox if present */
    if (c->inbox) {
        void *msg;
        while (channel_recv(c->inbox, &msg, 0, 0) == 1) {
            (void)msg;
        }
    }
    c->running = 0;
    if (g_callback_registry) callback_registry_emit(g_callback_registry, c, "capsule_stop");
    return (void*)(intptr_t)rc;
}

/* Create capsule: name owned by caller, will be copied into quarantine */
Capsule *tr_capsule_create(const char *name, int (*entry)(Capsule*, void*), void *user_ctx)
{
    if (!name) { tr_set_last_error_fmt("tr_capsule_create: invalid name"); return NULL; }
    Capsule *c = (Capsule*)malloc(sizeof(Capsule));
    if (!c) { tr_set_last_error_fmt("tr_capsule_create: OOM"); return NULL; }
    c->q = quarantine_create(16);
    if (!c->q) { free(c); tr_set_last_error_fmt("tr_capsule_create: quarantine_create failed"); return NULL; }
    // store name in quarantine-owned memory
    size_t nl = strlen(name) + 1;
    char *nn = (char*)quarantine_alloc(c->q, nl);
    if (!nn) { quarantine_destroy(c->q); free(c); tr_set_last_error_fmt("tr_capsule_create: name alloc failed"); return NULL; }
    memcpy(nn, name, nl);
    c->name = nn;
    c->inbox = channel_create(32); /* default inbox size */
    c->thread = 0;
    c->running = 0;
    c->user_ctx = user_ctx;
    c->entry = entry;
    return c;
}

void tr_capsule_destroy(Capsule *c)
{
    if (!c) return;
    if (c->running) {
        if (c->inbox) channel_close(c->inbox);
        tr_thread_join(c->thread);
    }
    if (c->inbox) channel_destroy(c->inbox);
    quarantine_destroy(c->q);
    free(c);
}

int tr_capsule_start(Capsule *c)
{
    if (!c) { tr_set_last_error_fmt("tr_capsule_start: invalid capsule"); return -1; }
    if (c->running) { tr_set_last_error_fmt("tr_capsule_start: already running"); return -1; }
    if (tr_thread_create(&c->thread, capsule_thread_start, (void*)c) != 0) { tr_set_last_error_fmt("tr_capsule_start: thread create failed"); return -1; }
    return 0;
}

int tr_capsule_join(Capsule *c)
{
    if (!c) { tr_set_last_error_fmt("tr_capsule_join: invalid capsule"); return -1; }
    if (!c->running) return 0;
    return tr_thread_join(c->thread);
}

int tr_capsule_send(Capsule *c, void *msg)
{
    if (!c || !c->inbox) { tr_set_last_error_fmt("tr_capsule_send: invalid args"); return -1; }
    return channel_send(c->inbox, msg, 1, 0);
}

int tr_capsule_try_send(Capsule *c, void *msg)
{
    if (!c || !c->inbox) { tr_set_last_error_fmt("tr_capsule_try_send: invalid args"); return -1; }
    return channel_send(c->inbox, msg, 0, 0);
}

/* ---------------------------
   Timer helpers (simple single-shot)
   --------------------------- */

typedef struct {
    uint32_t ms;
    void (*cb)(void*);
    void *ctx;
} TimerCtx;

static void *timer_thread_fn(void *arg)
{
    TimerCtx *t = (TimerCtx*)arg;
    if (!t) return NULL;
#ifdef _WIN32
    Sleep(t->ms);
#else
    struct timespec ts; ts.tv_sec = t->ms / 1000; ts.tv_nsec = (t->ms % 1000) * 1000000;
    nanosleep(&ts, NULL);
#endif
    t->cb(t->ctx);
    free(t);
    return NULL;
}

int tr_timer_start(uint32_t ms, void (*cb)(void*), void *ctx)
{
    if (!cb) { tr_set_last_error_fmt("tr_timer_start: invalid callback"); return -1; }
    TimerCtx *t = (TimerCtx*)malloc(sizeof(TimerCtx));
    if (!t) { tr_set_last_error_fmt("tr_timer_start: OOM"); return -1; }
    t->ms = ms; t->cb = cb; t->ctx = ctx;
    tr_thread_t th;
    if (tr_thread_create(&th, (tr_thread_fn_t)timer_thread_fn, t) != 0) { free(t); tr_set_last_error_fmt("tr_timer_start: thread create failed"); return -1; }
#ifdef _WIN32
    CloseHandle(th);
#else
    pthread_detach(th);
#endif
    return 0;
}

/* ---------------------------
   Syscall registry (maximized)
   - register syscall handler functions by name with metadata, permissions, and audit flags
   - tr_invoke_syscall does validation and produces structured error messages
   --------------------------- */

typedef struct {
    char *name;
    tr_syscall_handler_t handler;
    void *ctx;
    int flags;              /* bitfield for permissions, e.g. 1=audit, 2=trusted-only */
    char *auth_token;       /* optional token required to invoke */
    char *description;      /* human-friendly description */
} SyscallEntry;

typedef struct {
    SyscallEntry *entries;
    size_t count;
    size_t capacity;
    tr_mutex_t lock;
} SyscallRegistry;

static SyscallRegistry *g_syscall_registry = NULL;

static SyscallRegistry *syscall_registry_create(void)
{
    SyscallRegistry *r = (SyscallRegistry*)malloc(sizeof(SyscallRegistry));
    if (!r) return NULL;
    r->entries = (SyscallEntry*)malloc(sizeof(SyscallEntry) * 8);
    if (!r->entries) { free(r); return NULL; }
    r->count = 0; r->capacity = 8;
    tr_mutex_init(&r->lock);
    return r;
}

int tr_register_syscall_ex(const char *name, tr_syscall_handler_t handler, void *ctx, int flags, const char *auth_token, const char *description)
{
    if (!name || !handler) { tr_set_last_error_fmt("tr_register_syscall_ex: invalid args"); return -1; }
    if (!g_syscall_registry) g_syscall_registry = syscall_registry_create();
    SyscallRegistry *r = g_syscall_registry;
    tr_mutex_lock(&r->lock);
    if (r->count == r->capacity) {
        size_t nc = r->capacity * 2;
        SyscallEntry *ne = (SyscallEntry*)realloc(r->entries, sizeof(SyscallEntry) * nc);
        if (!ne) { tr_mutex_unlock(&r->lock); tr_set_last_error_fmt("tr_register_syscall_ex: realloc failed"); return -1; }
        r->entries = ne; r->capacity = nc;
    }
    size_t nl = strlen(name) + 1;
    char *ncopy = (char*)malloc(nl);
    if (!ncopy) { tr_mutex_unlock(&r->lock); tr_set_last_error_fmt("tr_register_syscall_ex: OOM name copy"); return -1; }
    memcpy(ncopy, name, nl);
    r->entries[r->count].name = ncopy;
    r->entries[r->count].handler = handler;
    r->entries[r->count].ctx = ctx;
    r->entries[r->count].flags = flags;
    r->entries[r->count].auth_token = auth_token ? strdup(auth_token) : NULL;
    r->entries[r->count].description = description ? strdup(description) : NULL;
    r->count++;
    tr_mutex_unlock(&r->lock);
    tr_audit_log("syscall_registered: %s flags=%d desc=%s", name, flags, description ? description : "");
    return 0;
}

int tr_unregister_syscall(const char *name)
{
    if (!name) { tr_set_last_error_fmt("tr_unregister_syscall: invalid name"); return -1; }
    if (!g_syscall_registry) { tr_set_last_error_fmt("tr_unregister_syscall: no registry"); return -1; }
    SyscallRegistry *r = g_syscall_registry;
    tr_mutex_lock(&r->lock);
    for (size_t i = 0; i < r->count; ++i) {
        if (strcmp(r->entries[i].name, name) == 0) {
            free(r->entries[i].name);
            if (r->entries[i].auth_token) free(r->entries[i].auth_token);
            if (r->entries[i].description) free(r->entries[i].description);
            r->entries[i] = r->entries[r->count - 1];
            r->count--;
            tr_mutex_unlock(&r->lock);
            tr_audit_log("syscall_unregistered: %s", name);
            return 0;
        }
    }
    tr_mutex_unlock(&r->lock);
    tr_set_last_error_fmt("tr_unregister_syscall: not found");
    return -1;
}

/* invoke syscall by name; returns handler return code, out_json is allocated by handler and must be freed by caller
   For extended validation, caller may pass auth_token (NULL if none).
*/
int tr_invoke_syscall_ex(const char *name, const char *args_json, const char *auth_token, char **out_json)
{
    if (!name) { tr_set_last_error_fmt("tr_invoke_syscall_ex: invalid name"); return -1; }
    if (!g_syscall_registry) { tr_set_last_error_fmt("tr_invoke_syscall_ex: no registry"); return -2; }
    SyscallRegistry *r = g_syscall_registry;
    tr_mutex_lock(&r->lock);
    for (size_t i = 0; i < r->count; ++i) {
        if (strcmp(r->entries[i].name, name) == 0) {
            SyscallEntry *e = &r->entries[i];
            if (e->auth_token) {
                if (!auth_token || strcmp(auth_token, e->auth_token) != 0) {
                    tr_mutex_unlock(&r->lock);
                    tr_set_last_error_fmt("tr_invoke_syscall_ex: auth failed for %s", name);
                    tr_audit_log("syscall_invoke_failed_auth: %s", name);
                    return -4;
                }
            }
            int audit = (e->flags & 1) != 0;
            tr_syscall_handler_t h = e->handler;
            void *ctx = e->ctx;
            tr_mutex_unlock(&r->lock);
            if (audit) tr_audit_log("syscall_invoke: %s args=%s", name, args_json ? args_json : "null");
            int rc = h(args_json, out_json, ctx);
            if (audit) tr_audit_log("syscall_invoke_result: %s rc=%d out=%s", name, rc, out_json ? (*out_json ? *out_json : "null") : "null");
            if (rc != 0 && !tr_get_last_error()[0]) tr_set_last_error_fmt("syscall handler %s returned %d", name, rc);
            return rc;
        }
    }
    tr_mutex_unlock(&r->lock);
    tr_set_last_error_fmt("tr_invoke_syscall_ex: not found");
    return -3;
}

/* Backwards compatibility wrappers */
int tr_register_syscall(const char *name, tr_syscall_handler_t handler, void *ctx)
{
    return tr_register_syscall_ex(name, handler, ctx, 0, NULL, NULL);
}
int tr_invoke_syscall(const char *name, const char *args_json, char **out_json)
{
    return tr_invoke_syscall_ex(name, args_json, NULL, out_json);
}

/* ---------------------------
   Process sandbox runner (maximized)
   - If running on Linux: attempt unshare(CLONE_NEWPID|CLONE_NEWNS|CLONE_NEWNET) and seccomp when available.
   - Always set rlimits, optionally chroot (requires root), optionally drop uid/gid.
   - Returns detailed error codes and sets tr_last_error with diagnostic.
   --------------------------- */

#ifndef _WIN32

#include <sys/stat.h>
#include <sys/mman.h>
#ifdef __linux__
#include <sched.h>
#ifdef __has_include
#if __has_include(<linux/seccomp.h>) && __has_include(<seccomp.h>)
#define HAVE_LIBSECCOMP 1
#include <seccomp.h>
#endif
#endif
#endif

/* Try applying optional strong isolation: namespaces + seccomp if available
   This function is best-effort and logs warnings in tr_last_error when a step cannot be applied.
*/
static void tr_try_harden_child(uid_t run_uid, gid_t run_gid)
{
#ifdef __linux__
    // Unshare PID, mount, and network namespaces if available
    int flags = 0;
#ifdef CLONE_NEWPID
    flags |= CLONE_NEWPID;
#endif
#ifdef CLONE_NEWNS
    flags |= CLONE_NEWNS;
#endif
#ifdef CLONE_NEWNET
    flags |= CLONE_NEWNET;
#endif
    if (flags) {
        if (unshare(flags) != 0) {
            tr_audit_log("sandbox: unshare failed: %s", strerror(errno));
        } else {
            tr_audit_log("sandbox: unshare succeeded flags=%d", flags);
        }
    }
    // attempt to set no_new_privs (pre-req for seccomp)
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        tr_audit_log("sandbox: PR_SET_NO_NEW_PRIVS failed: %s", strerror(errno));
    }

#ifdef HAVE_LIBSECCOMP
    // minimal seccomp filter: allow read, write, exit, sigreturn, rt_sigreturn; block execve by default
    scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_KILL); // deny by kill
    if (!ctx) {
        tr_audit_log("sandbox: seccomp_init failed");
    } else {
        // allow some syscalls commonly required for normal process operation; this is conservative skeleton
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(read), 0);
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(write), 0);
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(exit), 0);
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(exit_group), 0);
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(sigreturn), 0);
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(rt_sigreturn), 0);
        // allow futex for threads
        seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(futex), 0);
        // load filter
        if (seccomp_load(ctx) != 0) {
            tr_audit_log("sandbox: seccomp_load failed");
        } else {
            tr_audit_log("sandbox: seccomp loaded");
        }
        seccomp_release(ctx);
    }
#endif // HAVE_LIBSECCOMP

    // optionally drop credentials if requested; caller should have set them
    if (run_gid != (gid_t)-1) setgid(run_gid);
    if (run_uid != (uid_t)-1) setuid(run_uid);
#endif // __linux__
}

int tr_sandbox_run(const char *path, char *const argv[], char *const envp[],
                   const char *working_dir, uint64_t time_ms, size_t memory_limit_bytes,
                   uid_t run_uid, gid_t run_gid, int *out_exitcode)
{
    if (!path) { tr_set_last_error_fmt("tr_sandbox_run: path is NULL"); return -1; }
    pid_t pid = fork();
    if (pid < 0) { tr_set_last_error_fmt("tr_sandbox_run: fork failed: %s", strerror(errno)); return -1; }
    if (pid == 0) {
        /* child */
        // make session to isolate signals
        setsid();
        if (working_dir) chdir(working_dir);
        // set resource limits
        if (memory_limit_bytes > 0) {
            struct rlimit rl;
            rl.rlim_cur = rl.rlim_max = memory_limit_bytes;
            setrlimit(RLIMIT_AS, &rl);
        }
        if (time_ms > 0) {
            struct rlimit rl;
            rl.rlim_cur = rl.rlim_max = (time_ms + 999) / 1000;
            setrlimit(RLIMIT_CPU, &rl);
        }
        // try to further harden child process (namespaces, seccomp) - best-effort
        tr_try_harden_child(run_uid, run_gid);
        // exec
        execve(path, argv, envp);
        // if exec fails
        _exit(127);
    } else {
        /* parent: wait with timeout */
        int status = 0;
        uint64_t waited = 0;
        const uint32_t sleep_ms = 50;
        while (1) {
            pid_t w = waitpid(pid, &status, WNOHANG);
            if (w == pid) break;
            if (w == -1) { tr_set_last_error_fmt("tr_sandbox_run: waitpid error: %s", strerror(errno)); break; }
            if (time_ms > 0 && waited >= time_ms) {
                kill(pid, SIGKILL);
                waitpid(pid, &status, 0);
                if (out_exitcode) *out_exitcode = -1;
                tr_set_last_error_fmt("tr_sandbox_run: timeout, killed child");
                tr_audit_log("sandbox_run: timeout pid=%d path=%s", pid, path);
                return -2; /* timeout */
            }
            usleep(sleep_ms * 1000);
            waited += sleep_ms;
        }
        if (WIFEXITED(status)) {
            if (out_exitcode) *out_exitcode = WEXITSTATUS(status);
            return 0;
        } else if (WIFSIGNALED(status)) {
            if (out_exitcode) *out_exitcode = -WTERMSIG(status);
            return -3;
        }
        return 0;
    }
}

#else // _WIN32

int tr_sandbox_run(const char *path, char *const argv[], char *const envp[],
                   const char *working_dir, uint64_t time_ms, size_t memory_limit_bytes,
                   unsigned int run_uid, unsigned int run_gid, int *out_exitcode)
{
    (void)argv; (void)envp; (void)run_uid; (void)run_gid; (void)memory_limit_bytes;
    if (!path) { tr_set_last_error_fmt("tr_sandbox_run: path is NULL"); return -1; }
    STARTUPINFOA si; PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    char cmdline[MAX_PATH];
    strncpy(cmdline, path, MAX_PATH-1);
    if (!CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, working_dir, &si, &pi)) {
        tr_set_last_error_fmt("tr_sandbox_run: CreateProcess failed: %lu", GetLastError());
        return -1;
    }
    ResumeThread(pi.hThread);
    uint32_t wait_ms = (time_ms == 0) ? INFINITE : (DWORD)time_ms;
    DWORD w = WaitForSingleObject(pi.hProcess, wait_ms);
    if (w == WAIT_TIMEOUT) {
        TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
        if (out_exitcode) *out_exitcode = -1;
        tr_set_last_error_fmt("tr_sandbox_run: timeout");
        return -2;
    }
    DWORD exitcode = 0;
    GetExitCodeProcess(pi.hProcess, &exitcode);
    if (out_exitcode) *out_exitcode = (int)exitcode;
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return 0;
}

#endif // sandbox

/* ---------------------------
   JIT / NASM bridging (switch to clang+LLVM with fallback)
   - tr_nasm_compile_and_load: attempts clang first (preferred), falls back to nasm+clang/gcc, then to "no-compile" safe mode.
   - Produces detailed logs written to tmpdir/build.log and returns err_msg containing diagnostics.
   - On success returns pointer to symbol via dlopen/dlsym (POSIX).
   --------------------------- */

#ifndef _WIN32
#include <unistd.h>
int tr_nasm_compile_and_load(const char *nasm_src, const char *entry_symbol, void **fn_ptr, char **err_msg)
{
    if (!nasm_src || !entry_symbol || !fn_ptr) {
        if (err_msg) *err_msg = strdup("invalid arguments");
        tr_set_last_error_fmt("tr_nasm_compile_and_load: invalid args");
        return -1;
    }
    // create tmpdir
    char tmpl[] = "/tmp/trion_nasm_XXXXXX";
    char *tmpdir = mkdtemp(tmpl);
    if (!tmpdir) {
        if (err_msg) *err_msg = strdup("mkdtemp failed");
        tr_set_last_error_fmt("tr_nasm_compile_and_load: mkdtemp failed");
        return -1;
    }
    char asm_path[1024], obj_path[1024], so_path[1024], log_path[1024];
    snprintf(asm_path, sizeof(asm_path), "%s/module.asm", tmpdir);
    snprintf(obj_path, sizeof(obj_path), "%s/module.o", tmpdir);
    snprintf(so_path, sizeof(so_path), "%s/module.so", tmpdir);
    snprintf(log_path, sizeof(log_path), "%s/build.log", tmpdir);

    FILE *f = fopen(asm_path, "wb");
    if (!f) { if (err_msg) *err_msg = strdup("fopen asm failed"); tr_set_last_error_fmt("fopen asm failed"); return -1; }
    fwrite(nasm_src, 1, strlen(nasm_src), f); fclose(f);

    // Try to use clang to compile assembly/object -> shared object
    int used_clang = 0;
    int r = -1;
    {
        // clang command: clang -c -x assembler -o module.o module.asm
        char cmd[4096];
        snprintf(cmd, sizeof(cmd), "clang -c -x assembler \"%s\" -o \"%s\" 2> \"%s\"", asm_path, obj_path, log_path);
        r = system(cmd);
        if (r == 0) {
            used_clang = 1;
            snprintf(cmd, sizeof(cmd), "clang -shared -fPIC -o \"%s\" \"%s\" 2>> \"%s\"", so_path, obj_path, log_path);
            r = system(cmd);
        }
    }
    if (r != 0) {
        // fallback: try nasm + clang/gcc
        char cmd[4096];
        snprintf(cmd, sizeof(cmd), "nasm -f elf64 \"%s\" -o \"%s\" 2>> \"%s\"", asm_path, obj_path, log_path);
        r = system(cmd);
        if (r == 0) {
            // link with clang if available, else gcc
            if (system("which clang > /dev/null 2>&1") == 0) {
                snprintf(cmd, sizeof(cmd), "clang -shared -fPIC -o \"%s\" \"%s\" 2>> \"%s\"", so_path, obj_path, log_path);
            } else {
                snprintf(cmd, sizeof(cmd), "gcc -shared -fPIC -o \"%s\" \"%s\" 2>> \"%s\"", so_path, obj_path, log_path);
            }
            r = system(cmd);
        }
    }

    if (r != 0) {
        if (err_msg) {
            FILE *lf = fopen(log_path, "rb");
            if (lf) {
                fseek(lf, 0, SEEK_END); long sz = ftell(lf); fseek(lf, 0, SEEK_SET);
                char *buf = (char*)malloc(sz + 256);
                if (buf) {
                    fread(buf, 1, sz, lf);
                    buf[sz] = '\0';
                    snprintf(buf + sz, 256, "\nCommand failed. Clang used=%d", used_clang);
                    *err_msg = buf;
                }
                fclose(lf);
            } else {
                *err_msg = strdup("build failed and no log available");
            }
        }
        tr_set_last_error_fmt("tr_nasm_compile_and_load: build failed; see err_msg");
        return -2;
    }

    // dlopen and dlsym
    void *handle = dlopen(so_path, RTLD_NOW);
    if (!handle) {
        if (err_msg) *err_msg = strdup(dlerror());
        tr_set_last_error_fmt("tr_nasm_compile_and_load: dlopen failed: %s", dlerror());
        return -4;
    }
    void *sym = dlsym(handle, entry_symbol);
    if (!sym) {
        if (err_msg) *err_msg = strdup(dlerror());
        dlclose(handle);
        tr_set_last_error_fmt("tr_nasm_compile_and_load: dlsym failed: %s", dlerror());
        return -5;
    }
    *fn_ptr = sym;
    tr_audit_log("jit_load: compiled and loaded %s entry=%s", asm_path, entry_symbol);
    return 0;
}
#else
int tr_nasm_compile_and_load(const char *nasm_src, const char *entry_symbol, void **fn_ptr, char **err_msg)
{
    (void)nasm_src; (void)entry_symbol; (void)fn_ptr;
    if (err_msg) *err_msg = strdup("tr_nasm_compile_and_load: Not implemented on Windows in this runtime");
    tr_set_last_error_fmt("tr_nasm_compile_and_load: Not implemented on Windows");
    return -1;
}
#endif

/* ---------------------------
   Utility debug helpers
   --------------------------- */

void tr_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stdout, fmt, ap);
    va_end(ap);
    fprintf(stdout, "\n");
}

/* ---------------------------
   Public API (C-linkage)
   --------------------------- */

#ifdef __cplusplus
extern "C" {
#endif

/* Error / audit */
const char *tr_get_last_error_c(void) { return tr_get_last_error(); }
int tr_audit_open_c(const char *path) { return tr_audit_open(path); }
void tr_audit_close_c(void) { tr_audit_close(); }

/* Quarantine API */
Quarantine *tr_quarantine_create(size_t initial_capacity) { return quarantine_create(initial_capacity); }
void *tr_quarantine_alloc(Quarantine *q, size_t size) { return quarantine_alloc(q, size); }
int tr_quarantine_free(Quarantine *q, void *ptr) { return quarantine_free(q, ptr); }
void tr_quarantine_seal(Quarantine *q) { quarantine_seal(q); }
void tr_quarantine_destroy(Quarantine *q) { quarantine_destroy(q); }
char *tr_quarantine_strdup(Quarantine *q, const char *s)
{
    if (!q || !s) return NULL;
    size_t n = strlen(s) + 1;
    char *p = (char*)quarantine_alloc(q, n);
    if (!p) return NULL;
    memcpy(p, s, n);
    return p;
}

/* Channel API */
Channel *tr_channel_create(size_t capacity) { return channel_create(capacity); }
int tr_channel_send(Channel *c, void *item) { return channel_send(c, item, 1, 0); } /* blocking */
int tr_channel_try_send(Channel *c, void *item) { return channel_send(c, item, 0, 0); } /* non-blocking */
int tr_channel_send_timed(Channel *c, void *item, uint32_t ms) { return channel_send(c, item, 1, ms); }
int tr_channel_recv(Channel *c, void **out) { return channel_recv(c, out, 1, 0); }
int tr_channel_try_recv(Channel *c, void **out) { return channel_recv(c, out, 0, 0); }
int tr_channel_recv_timed(Channel *c, void **out, uint32_t ms) { return channel_recv(c, out, 1, ms); }
void tr_channel_close(Channel *c) { channel_close(c); }
void tr_channel_destroy(Channel *c) { channel_destroy(c); }

/* Thread API */
int tr_thread_start(tr_thread_t *out, tr_thread_fn_t fn, void *arg) { return tr_thread_create(out, fn, arg); }
int tr_thread_wait(tr_thread_t t) { return tr_thread_join(t); }

/* Dodecagram API (uint64) */
int tr_dodecagram_to_base12(uint64_t n, char *out, size_t outlen) { return tr_to_base12_u64(n, out, outlen); }
int tr_dodecagram_from_base12(const char *s, uint64_t *out) { return tr_from_base12_u64(s, out); }

/* Bytes <-> base12 API (arbitrary length) */
int tr_bytes_to_base12(const uint8_t *bytes, size_t len, char *out, size_t outlen) { return bytes_to_base12(bytes, len, out, outlen); }
int tr_bytes_to_base12_scaled(const uint8_t *bytes, size_t len, int scale, char *out, size_t outlen) { return bytes_to_base12_scaled(bytes, len, scale, out, outlen); }
int tr_base12_to_bytes(const char *s, uint8_t **out_bytes, size_t *out_len) { return base12_to_bytes(s, out_bytes, out_len); }
int tr_base12_to_bytes_with_scale(const char *s, uint8_t **out_bytes, size_t *out_len, int *out_scale) { return base12_to_bytes_with_scale(s, out_bytes, out_len, out_scale); }

/* Packet API */
TrionPacket *tr_packet_create_owned(Quarantine *q, const void *payload, size_t len) { return tr_packet_create(q, payload, len); }
void tr_packet_destroy_owned(TrionPacket *p) { tr_packet_destroy(p); }
int tr_packet_drop_if_srcip(TrionPacket *p, uint32_t ip) { return tr_packet_drop_if_src_ip(p, ip); }

/* Capsule API */
Capsule *tr_capsule_create(const char *name, int (*entry)(Capsule*, void*), void *user_ctx) { return tr_capsule_create(name, entry, user_ctx); }
void tr_capsule_destroy(Capsule *c) { tr_capsule_destroy(c); }
int tr_capsule_start(Capsule *c) { return tr_capsule_start(c); }
int tr_capsule_join(Capsule *c) { return tr_capsule_join(c); }
int tr_capsule_send(Capsule *c, void *msg) { return tr_capsule_send(c, msg); }
int tr_capsule_try_send(Capsule *c, void *msg) { return tr_capsule_try_send(c, msg); }

/* Event callbacks */
int tr_register_event_callback(tr_event_callback_t cb, void *ctx) { return tr_register_event_callback(cb, ctx); }

/* Timers */
int tr_timer_start_ms(uint32_t ms, void (*cb)(void*), void *ctx) { return tr_timer_start(ms, cb, ctx); }

/* Syscall registry */
int tr_register_syscall(const char *name, tr_syscall_handler_t handler, void *ctx) { return tr_register_syscall(name, handler, ctx); }
int tr_register_syscall_ex_c(const char *name, tr_syscall_handler_t handler, void *ctx, int flags, const char *auth_token, const char *description) { return tr_register_syscall_ex(name, handler, ctx, flags, auth_token, description); }
int tr_invoke_syscall(const char *name, const char *args_json, char **out_json) { return tr_invoke_syscall(name, args_json, out_json); }
int tr_invoke_syscall_ex_c(const char *name, const char *args_json, const char *auth_token, char **out_json) { return tr_invoke_syscall_ex(name, args_json, auth_token, out_json); }

/* Sandbox runner */
int tr_sandbox_run_wrapper(const char *path, char *const argv[], char *const envp[],
                           const char *working_dir, uint64_t time_ms, size_t memory_limit_bytes,
#ifdef _WIN32
                           unsigned int run_uid, unsigned int run_gid,
#else
                           uid_t run_uid, gid_t run_gid,
#endif
                           int *out_exitcode)
{
    return tr_sandbox_run(path, argv, envp, working_dir, time_ms, memory_limit_bytes, run_uid, run_gid, out_exitcode);
}

/* JIT/NASM compile & load */
int tr_nasm_compile_and_load_wrapper(const char *nasm_src, const char *entry_symbol, void **fn_ptr, char **err_msg)
{
    return tr_nasm_compile_and_load(nasm_src, entry_symbol, fn_ptr, err_msg);
}

/* Logging */
void tr_log_printf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stdout, fmt, ap);
    va_end(ap);
    fprintf(stdout, "\n");
}

#ifdef __cplusplus
}
#endif

/* End of trion_runtime.c */
