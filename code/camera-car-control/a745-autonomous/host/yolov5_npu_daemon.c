/* YOLOv5 raw-head decoder for the HHB 2.4.5 TH1520 graph binary.
 * Build with the matching CSI-NN headers and libshl_th1520.so.2.
 * stdin contains float32 RGB NCHW file paths, one per line; QUIT ends.
 * Input is fixed at 1x3x384x640, normalized to [0,1].
 */
#include <csinn_runtime.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

extern void *shl_mem_alloc_aligned(int64_t, int);
extern void shl_mem_free(void *);
extern uint8_t *shl_ref_f32_to_input_dtype(uint32_t, float *, struct csinn_session *);

#define ELEMENTS (3 * 384 * 640)
#define CAPACITY 15120
struct box { float x1,y1,x2,y2,score; int label; };
static struct box candidates[CAPACITY];
static volatile sig_atomic_t stopping;
static void stop(int sig) { (void)sig; stopping=1; }
static double now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return t.tv_sec+t.tv_nsec*1e-9;
}
static float sigmoid(float v) { return 1.0f/(1.0f+expf(-v)); }
static int compare(const void *a,const void *b) {
    float x=((const struct box *)a)->score, y=((const struct box *)b)->score;
    return (x<y)-(x>y);
}
static float iou(struct box a,struct box b) {
    float w=fmaxf(0,fminf(a.x2,b.x2)-fmaxf(a.x1,b.x1));
    float h=fmaxf(0,fminf(a.y2,b.y2)-fmaxf(a.y1,b.y1));
    float intersection=w*h;
    float total=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-intersection;
    return total>0?intersection/total:0;
}
static float value(const struct csinn_tensor *t,int channel,int index,int plane) {
    int pos=channel*plane+index;
    if(t->dtype==CSINN_DTYPE_FLOAT32) return ((float *)t->data)[pos];
    int q=t->dtype==CSINN_DTYPE_INT8 ? ((int8_t *)t->data)[pos] : ((uint8_t *)t->data)[pos];
    const struct csinn_quant_info *qi=t->qinfo+(t->quant_channel>1?channel:0);
    return (q-qi->zero_point)*qi->scale;
}
static int decode(struct csinn_session *sess,float conf,float nms) {
    const float anchors[3][3][2]={{{10,13},{16,30},{33,23}},
                                  {{30,61},{62,45},{59,119}},
                                  {{116,90},{156,198},{373,326}}};
    int count=0, heads=csinn_get_output_number(sess);
    unsigned head_mask=0;
    if(heads!=3) return -1;
    for(int k=0;k<heads;k++) {
        struct csinn_tensor *t=csinn_alloc_tensor(NULL);
        csinn_get_output(k,t,sess);
        int h=t->dim[2],w=t->dim[3],head=-1;
        for(int j=0;j<3;j++) if(h==384/(8<<j)&&w==640/(8<<j)) head=j;
        if(t->dim_count!=4||t->dim[0]!=1||t->dim[1]!=255||head<0||
           (head_mask&(1u<<head))||!t->data||
           (t->dtype!=CSINN_DTYPE_INT8&&t->dtype!=CSINN_DTYPE_UINT8&&t->dtype!=CSINN_DTYPE_FLOAT32)||
           (t->dtype!=CSINN_DTYPE_FLOAT32&&(!t->qinfo||t->quant_channel<1))) {
            fprintf(stderr,"invalid raw detection head %d\n",k); csinn_free_tensor(t); return -1;
        }
        head_mask |= 1u<<head;
        if(getenv("YOLO_DUMP_HEADS")) {
            char path[128]; snprintf(path,sizeof path,"/tmp/fpga-yolo-head-%d.f32",head);
            FILE *f=fopen(path,"wb");
            if(f) { for(int c=0;c<255;c++) for(int p=0;p<h*w;p++) {
                float v=value(t,c,p,h*w); fwrite(&v,sizeof v,1,f);
            } fclose(f); }
        }
        int plane=h*w,stride=8<<head;
        for(int a=0;a<3;a++) for(int p=0;p<plane;p++) {
            int channel=a*85;
            float obj=sigmoid(value(t,channel+4,p,plane));
            if(obj<conf) continue;
            int label=0; float best=-INFINITY;
            for(int c=0;c<80;c++) {
                float v=value(t,channel+5+c,p,plane);
                if(v>best) {best=v;label=c;}
            }
            float score=obj*sigmoid(best);
            if(score<conf) continue;
            float sx=sigmoid(value(t,channel,p,plane));
            float sy=sigmoid(value(t,channel+1,p,plane));
            float sw=2*sigmoid(value(t,channel+2,p,plane));
            float sh=2*sigmoid(value(t,channel+3,p,plane));
            /* YOLOv5: xy=(sigmoid*2-.5+grid)*stride;
             * wh=(sigmoid*2)^2*anchor. exp(logit)*anchor is YOLOv3. */
            float x=(sx*2-.5f+p%w)*stride,y=(sy*2-.5f+p/w)*stride;
            float bw=sw*sw*anchors[head][a][0],bh=sh*sh*anchors[head][a][1];
            if(count>=CAPACITY) {csinn_free_tensor(t);return -1;}
            candidates[count++]=(struct box){x-bw/2,y-bh/2,x+bw/2,y+bh/2,score,label};
        }
        csinn_free_tensor(t);
    }
    qsort(candidates,count,sizeof candidates[0],compare);
    struct box kept[64]; int n=0;
    for(int i=0;i<count&&n<64;i++) {
        int suppressed=0;
        for(int j=0;j<n;j++) if(candidates[i].label==kept[j].label&&iou(candidates[i],kept[j])>nms) {
            suppressed=1;break;
        }
        if(!suppressed) kept[n++]=candidates[i];
    }
    printf("DET %d\n",n);
    for(int i=0;i<n;i++) printf("%d %.4f %.2f %.2f %.2f %.2f\n",kept[i].label,
        kept[i].score,kept[i].x1,kept[i].y1,kept[i].x2,kept[i].y2);
    puts("END"); fflush(stdout); return 0;
}
int main(int argc,char **argv) {
    if(argc<2) {fprintf(stderr,"usage: %s shl.hhb.bm [conf] [iou]\n",argv[0]);return 2;}
    float conf=argc>2?strtof(argv[2],NULL):.30f,nms=argc>3?strtof(argv[3],NULL):.45f;
    if(!(conf>0&&conf<1&&nms>0&&nms<1)) return 2;
    struct sigaction action={0}; action.sa_handler=stop; sigemptyset(&action.sa_mask);
    sigaction(SIGTERM,&action,NULL); sigaction(SIGINT,&action,NULL);
    setvbuf(stdout,NULL,_IOLBF,0);
    FILE *f=fopen(argv[1],"rb"); if(!f) {perror("model");return 2;}
    fseek(f,0,SEEK_END); long bytes=ftell(f); rewind(f);
    void *model=bytes>0?malloc(bytes):NULL;
    if(!model||fread(model,1,bytes,f)!=(size_t)bytes) {fclose(f);return 2;}
    fclose(f);
    struct csinn_session *sess=csinn_import_binary_model(model);
    if(!sess||sess->input_num!=1) {fprintf(stderr,"model import failed\n");return 3;}
    struct csinn_tensor *input=csinn_alloc_tensor(NULL);
    csinn_get_input(0,input,sess);
    if(input->dim_count!=4||input->dim[0]!=1||input->dim[1]!=3||
       input->dim[2]!=384||input->dim[3]!=640) {fprintf(stderr,"invalid input shape\n");return 3;}
    int input_bytes=csinn_tensor_byte_size(input);
    void *aligned=shl_mem_alloc_aligned(input_bytes,0);
    float *fp=malloc(ELEMENTS*sizeof(float));
    if(!aligned||!fp) return 3;
    char path[4096]; int result=0;
    printf("READY %d\n",input_bytes);
    while(!stopping&&fgets(path,sizeof path,stdin)) {
        path[strcspn(path,"\r\n")]=0;
        if(!strcmp(path,"QUIT")) break;
        f=fopen(path,"rb");
        if(!f) {puts("ERROR input file");continue;}
        size_t n=fread(fp,sizeof(float),ELEMENTS,f); int extra=fgetc(f); fclose(f);
        if(n!=ELEMENTS||extra!=EOF) {puts("ERROR input length");continue;}
        uint8_t *quant=shl_ref_f32_to_input_dtype(0,fp,sess);
        if(!quant) {puts("ERROR input quantization");result=4;break;}
        memcpy(aligned,quant,input_bytes); shl_mem_free(quant); input->data=aligned;
        double start=now(); csinn_update_input(0,input,sess); csinn_session_run(sess);
        printf("TIME %.3f\n",(now()-start)*1000);
        if(decode(sess,conf,nms)<0) {puts("ERROR output layout");result=4;break;}
    }
    csinn_session_deinit(sess); csinn_free_session(sess);
    csinn_free_tensor(input); shl_mem_free(aligned); free(fp); free(model);
    return result;
}
