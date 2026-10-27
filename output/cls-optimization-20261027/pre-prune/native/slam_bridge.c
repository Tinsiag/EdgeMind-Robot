/* EdgeMind adapter for the dynamically linked LGPL CoreSLAM library.
 * The upstream sources and both license texts are in third_party/coreslam. */
#include <stdlib.h>
#include <math.h>
#include "coreslam.h"
#include "random.h"
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API
#endif
typedef struct {
    map_t map;
    scan_t scan;
    position_t pose;
    void *random;
    int frames;
} engine_t;

API void *em_create(int pixels, double meters) {
    if (pixels < 100 || pixels > 2000 || meters < 5 || meters > 100) return NULL;
    engine_t *e = calloc(1, sizeof(engine_t));
    if (!e) return NULL;
    map_init(&e->map, pixels, meters);
    /* 361 entries give exactly one degree per ray. No-return rays have length 0,
       so unobserved directions cannot invent free space out to maximum range. */
    scan_init(&e->scan, 1, 361, 10, 360, 0, 0, 0);
    e->pose.x_mm = e->pose.y_mm = meters * 500;
    e->random = random_new(741);
    return e;
}
API void em_free(void *handle) {
    engine_t *e = handle;
    if (!e) return;
    scan_free(&e->scan); map_free(&e->map); random_free(e->random); free(e);
}
API int em_update(void *handle, int *ranges, double distance, double angle, double dt) {
    engine_t *e = handle;
    if (!e || !ranges || !isfinite(distance) || !isfinite(angle) || dt < 0 || dt > 1) return 0;
    double radians = (e->pose.theta_degrees + angle / 2) * 3.141592653589793 / 180;
    position_t predicted = e->pose;
    predicted.x_mm += distance * cos(radians);
    predicted.y_mm += distance * sin(radians);
    predicted.theta_degrees += angle;
    /* Full-turn timestamps are coarse. Do not invent per-ray deskew timing. */
    scan_update(&e->scan, NULL, ranges, 361, 200, 0, 0);
    /* Upstream zero-range rays are not valid free-space observations. Drop
       them before map_update (which divides by ray length). */
    int kept = 0;
    for (int i=0; i<e->scan.npoints; i++) {
        if (fabs(e->scan.x_mm[i])+fabs(e->scan.y_mm[i]) < 1) continue;
        e->scan.x_mm[kept] = e->scan.x_mm[i];
        e->scan.y_mm[kept] = e->scan.y_mm[i];
        e->scan.value[kept++] = e->scan.value[i];
    }
    e->scan.npoints = kept;
    if (e->scan.obst_npoints < 30) return 0;
    position_t candidate = predicted;
    if (e->frames > 3) candidate = rmhc_position_search(predicted, &e->map, &e->scan, 40, 2, 300, e->random);
    /* Reject unconstrained jumps rather than corrupting an accumulated map. */
    if (fabs(candidate.x_mm-predicted.x_mm) > 250 || fabs(candidate.y_mm-predicted.y_mm) > 250 ||
        fabs(candidate.theta_degrees-predicted.theta_degrees) > 12) return 0;
    if (candidate.x_mm < 500 || candidate.y_mm < 500 ||
        candidate.x_mm > e->map.size_meters*1000-500 || candidate.y_mm > e->map.size_meters*1000-500) return 0;
    e->pose = candidate;
    map_update(&e->map, &e->scan, candidate, 50, 200);
    e->frames++;
    return 1;
}
API void em_map(void *handle, char *pixels) { map_get(&((engine_t *)handle)->map, pixels); }
API void em_pose(void *handle, double *pose) {
    engine_t *e = handle; pose[0]=e->pose.x_mm;pose[1]=e->pose.y_mm;pose[2]=e->pose.theta_degrees;
}
