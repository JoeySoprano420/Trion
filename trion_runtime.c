// Runtime logic for Trion language
// Lightweight, portable quarantine memory and channel primitives.
// Designed for embedding in the Trion compiler/runtime.
// Author: GitHub Copilot

#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
typedef CRITICAL_SECTION tr_mutex_t;
typedef CONDITION_VARIABLE tr_cond_t;
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
typedef pthread_mutex_t tr_mutex_t;
typedef pthread_cond_t tr_cond_t;
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
    // macOS doesn't have clock_gettime on older SDKs; fall back to time()
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
   Quarantine: tracked allocations per capsule/quarantine
   --------------------------- */

typedef struct {
    void **items;
    size_t count;
    size_t capacity;
    int sealed;     /* once sealed, new allocations are rejected */
    tr_mutex_t lock;
} Quarantine;

/* Create a quarantine. Returns NULL on OOM. */
Quarantine *quarantine_create(size_t initial_capacity)
{
    Quarantine *q = (Quarantine*)malloc(sizeof(Quarantine));
    if (!q) return NULL;
    q->capacity = initial_capacity ? initial_capacity : 16;
    q->count = 0;
    q->sealed = 0;
    q->items = (void**)calloc(q->capacity, sizeof(void*));
    if (!q->items) { free(q); return NULL; }
    tr_mutex_init(&q->lock);
    return q;
}

/* Internal grow */
static int quarantine_grow_if_needed(Quarantine *q)
{
    if (q->count < q->capacity) return 0;
    size_t newcap = q->capacity * 2;
    void **n = (void**)realloc(q->items, newcap * sizeof(void*));
    if (!n) return -1;
    q->items = n;
    q->capacity = newcap;
    return 0;
}

/* Allocate memory registered to this quarantine.
   Returns pointer or NULL on failure / if sealed. */
void *quarantine_alloc(Quarantine *q, size_t size)
{
    if (!q || size == 0) return NULL;
    tr_mutex_lock(&q->lock);
    if (q->sealed) {
        tr_mutex_unlock(&q->lock);
        return NULL;
    }
    if (quarantine_grow_if_needed(q) != 0) {
        tr_mutex_unlock(&q->lock);
        return NULL;
    }
    void *p = malloc(size);
    if (!p) { tr_mutex_unlock(&q->lock); return NULL; }
    q->items[q->count++] = p;
    tr_mutex_unlock(&q->lock);
    return p;
}

/* Free a single allocation registered in the quarantine.
   Returns 0 on success, -1 if not found. */
int quarantine_free(Quarantine *q, void *ptr)
{
    if (!q || !ptr) return -1;
    tr_mutex_lock(&q->lock);
    for (size_t i = 0; i < q->count; ++i) {
        if (q->items[i] == ptr) {
            free(ptr);
            /* compact list */
            q->items[i] = q->items[q->count - 1];
            q->items[q->count - 1] = NULL;
            q->count--;
            tr_mutex_unlock(&q->lock);
            return 0;
        }
    }
    tr_mutex_unlock(&q->lock);
    return -1;
}

/* Seal the quarantine - disallow new allocations. */
void quarantine_seal(Quarantine *q)
{
    if (!q) return;
    tr_mutex_lock(&q->lock);
    q->sealed = 1;
    tr_mutex_unlock(&q->lock);
}

/* Destroy quarantine and free all tracked allocations. */
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

/* ---------------------------
   Channel: fixed-capacity MPMC (multi-producer multi-consumer)
   Simple blocking/non-blocking send/recv with optional timeout.
   --------------------------- */

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

/* Create a channel with capacity > 0. Returns NULL on OOM or invalid cap. */
Channel *channel_create(size_t capacity)
{
    if (capacity == 0) return NULL;
    Channel *c = (Channel*)malloc(sizeof(Channel));
    if (!c) return NULL;
    c->buffer = (void**)calloc(capacity, sizeof(void*));
    if (!c->buffer) { free(c); return NULL; }
    c->capacity = capacity;
    c->head = c->tail = c->count = 0;
    c->closed = 0;
    tr_mutex_init(&c->lock);
    tr_cond_init(&c->not_empty);
    tr_cond_init(&c->not_full);
    return c;
}

/* Close channel: wake all waiters; subsequent sends fail, receives drain then return 0. */
void channel_close(Channel *c)
{
    if (!c) return;
    tr_mutex_lock(&c->lock);
    c->closed = 1;
    tr_cond_notify_all(&c->not_empty);
    tr_cond_notify_all(&c->not_full);
    tr_mutex_unlock(&c->lock);
}

/* Destroy channel and free buffer. Caller must ensure no threads are blocked or using channel. */
void channel_destroy(Channel *c)
{
    if (!c) return;
    free(c->buffer);
    tr_cond_destroy(&c->not_empty);
    tr_cond_destroy(&c->not_full);
    tr_mutex_destroy(&c->lock);
    free(c);
}

/* Send an item into channel.
   blocking: 1 = block until space or closed; 0 = non-blocking (returns -2 if full).
   timeout_ms: if >0 and blocking, will wait up to timeout; 0 = indefinite.
   Returns 0 on success, -1 on error (closed), -2 if non-blocking and full, -3 on timeout. */
int channel_send(Channel *c, void *item, int blocking, uint32_t timeout_ms)
{
    if (!c) return -1;
    tr_mutex_lock(&c->lock);
    if (c->closed) { tr_mutex_unlock(&c->lock); return -1; }
    while (c->count == c->capacity) {
        if (!blocking) { tr_mutex_unlock(&c->lock); return -2; }
        if (timeout_ms == 0) {
            /* wait indefinitely */
            tr_cond_wait(&c->not_full, &c->lock);
        } else {
            int w = tr_cond_timedwait(&c->not_full, &c->lock, timeout_ms);
            if (w != 0) { tr_mutex_unlock(&c->lock); return -3; }
        }
        if (c->closed) { tr_mutex_unlock(&c->lock); return -1; }
    }
    c->buffer[c->tail] = item;
    c->tail = (c->tail + 1) % c->capacity;
    c->count++;
    tr_cond_notify_one(&c->not_empty);
    tr_mutex_unlock(&c->lock);
    return 0;
}

/* Receive an item from channel.
   blocking semantics same as channel_send.
   out receives item pointer. Returns:
     1 on success (item filled),
     0 if channel closed and drained (no item),
    -2 if non-blocking and empty,
    -3 on timeout,
    -1 on other error.
*/
int channel_recv(Channel *c, void **out, int blocking, uint32_t timeout_ms)
{
    if (!c || !out) return -1;
    tr_mutex_lock(&c->lock);
    while (c->count == 0) {
        if (c->closed) { tr_mutex_unlock(&c->lock); return 0; }
        if (!blocking) { tr_mutex_unlock(&c->lock); return -2; }
        if (timeout_ms == 0) {
            tr_cond_wait(&c->not_empty, &c->lock);
        } else {
            int w = tr_cond_timedwait(&c->not_empty, &c->lock, timeout_ms);
            if (w != 0) { tr_mutex_unlock(&c->lock); return -3; }
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
   Simple runtime helpers
   --------------------------- */

/* Allocate a duplicate string in a quarantine (convenience). */
char *quarantine_strdup(Quarantine *q, const char *s)
{
    if (!s) return NULL;
    size_t n = strlen(s) + 1;
    char *p = (char*)quarantine_alloc(q, n);
    if (!p) return NULL;
    memcpy(p, s, n);
    return p;
}

/* Debug helpers (print status) */
void quarantine_debug(Quarantine *q)
{
    if (!q) return;
    tr_mutex_lock(&q->lock);
    fprintf(stderr, "[quarantine] items=%zu capacity=%zu sealed=%d\n", q->count, q->capacity, q->sealed);
    tr_mutex_unlock(&q->lock);
}

void channel_debug(Channel *c)
{
    if (!c) return;
    tr_mutex_lock(&c->lock);
    fprintf(stderr, "[channel] cap=%zu count=%zu closed=%d head=%zu tail=%zu\n", c->capacity, c->count, c->closed, c->head, c->tail);
    tr_mutex_unlock(&c->lock);
}

/* ---------------------------
   Example public API naming for Trion runtime integration
   (kept C-linkage friendly)
   --------------------------- */

#ifdef __cplusplus
extern "C" {
#endif

/* Quarantine API */
Quarantine *tr_quarantine_create(size_t initial_capacity) { return quarantine_create(initial_capacity); }
void *tr_quarantine_alloc(Quarantine *q, size_t size) { return quarantine_alloc(q, size); }
int tr_quarantine_free(Quarantine *q, void *ptr) { return quarantine_free(q, ptr); }
void tr_quarantine_seal(Quarantine *q) { quarantine_seal(q); }
void tr_quarantine_destroy(Quarantine *q) { quarantine_destroy(q); }
char *tr_quarantine_strdup(Quarantine *q, const char *s) { return quarantine_strdup(q, s); }

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

#ifdef __cplusplus
}
#endif
/* End of trion_runtime.c */
