/* PS2 name-entry IME. Freestanding MIPS II; no heap, OS or libc. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
#include "tables.h"
#define WORD(p,o) (*(u32 *)((u8 *)(p)+(o)))
#define CURSOR (*(volatile int *)0x1fb0a48)
extern void cursor_fx(u32,int,int,int);
static void *owner;
static int initial=-1, vowel=-1, final=0, pending=-1;
static int history_l[8],history_v[8],history_t[8],history_n;
static u8 letters[12][4];
static const u16 initials[]={0x3131,0x3132,0x3134,0x3137,0x3138,0x3139,0x3141,0x3142,0x3143,0x3145,0x3146,0x3147,0x3148,0x3149,0x314a,0x314b,0x314c,0x314d,0x314e};
static const u16 finals[]={0,0x3131,0x3132,0x3133,0x3134,0x3135,0x3136,0x3137,0x3139,0x313a,0x313b,0x313c,0x313d,0x313e,0x313f,0x3140,0x3141,0x3142,0x3144,0x3145,0x3146,0x3147,0x3148,0x314a,0x314b,0x314c,0x314d,0x314e};
static const u8 split1[]={0,0,1,1,0,4,4,0,0,8,8,8,8,8,8,8,0,0,17,0,19,0,0,0,0,0,0,0};
static const u8 split2[]={0,1,1,19,4,22,27,7,8,1,16,17,19,25,26,27,16,17,19,19,19,21,22,23,24,25,26,27};

unsigned glyph_lookup(unsigned code) {
 unsigned hi=code>>8, lo=code&255, k;
 if(hi>=0x81 && hi<0xa0) k=(hi-0x81)*256+lo;
 else if(hi>=0xe0 && hi<0xeb) k=(hi-0xc1)*256+lo;
 else if(hi>=0xed && hi<0xef) k=(hi-0xc3)*256+lo;
 else if(hi==0xef) k=(hi-0xc4)*256+lo;
 else return 65535;
 for(unsigned i=0;i<RANGE_COUNT;i++)
  if(k>=ranges[i][0] && k<ranges[i][0]+ranges[i][1]) return ranges[i][2]+k-ranges[i][0];
 return 65535;
}
static int lead(unsigned c) {return (c>=0x81 && c<0xa0)||(c>=0xe0 && c<0xf0);}
static int bytes(const u8 *s) {int n=0;while(n<11 && s[n]) n++;return n;}
static int span(const u8 *s,int p) {return lead(s[p]) && p<10 && s[p+1]?2:1;}
static int nchars(const u8 *s) {int i=0,n=0;while(i<11 && s[i]) {i+=span(s,i);n++;}return n;}
static int offset(const u8 *s,int pos) {int i=0;while(pos-->0 && i<11 && s[i])i+=span(s,i);return i;}
static u16 unicode(u16 code) {for(unsigned i=0;i<CHAR_COUNT;i++)if(codes[i]==code)return chars[i];return 0;}
static u16 encoded(u16 u) {int lo=0,hi=CHAR_COUNT;while(lo<hi){int m=(lo+hi)/2;if(chars[m]<u)lo=m+1;else hi=m;}return lo<CHAR_COUNT && chars[lo]==u?codes[lo]:0;}
static int indexof(const u16 *a,int n,u16 c) {for(int i=0;i<n;i++)if(a[i]==c)return i;return -1;}
static void commit(void){initial=-1;vowel=-1;final=0;pending=-1;history_n=0;}
static void ensure(void *p){if(owner!=p){owner=p;commit();}}
static u32 floatint(unsigned x) {if(!x)return 0;unsigned n=0,t=x;while(t>>1){t>>=1;n++;}return ((n+127)<<23)|((x<<(23-n))&0x7fffff);}
static void sound(int reject){((void(*)(int,int))0x1a3d40)(reject?0x55:0x53,1);}
void refresh(void *p) {
 u8 *s=(u8 *)p+0x1500;int at=0,x=WORD(p,0x1514)-2;
 for(int i=0;i<12;i++) {
  int n=at<11 && s[at]?span(s,at):0;
  letters[i][0]=n?s[at]:0;letters[i][1]=n==2?s[at+1]:0;letters[i][2]=0;
  u32 obj=WORD(p,0x153c+i*16);
  if(obj){((void(*)(u32,u8*))0x13f4b0)(obj,letters[i]);WORD(obj,4)=floatint(x);}
  WORD(p,0x1530+i*16)=0;WORD(p,0x1534+i*16)=0;WORD(p,0x1538+i*16)=0;
  if(n){at+=n;x+=n==2?18:16;}
 }
 int count=nchars(s);if(CURSOR<0)CURSOR=0;if(CURSOR>count)CURSOR=count;
 ((void(*)(void*))0x5e1370)(p);
}
void setup(void *p){owner=p;commit();CURSOR=0;refresh(p);}
void frame(void *p){
 ((void(*)(void*))0x1d4540)(p);
 u8 *s=(u8 *)p+0x1500;int at=0,x=WORD(p,0x1514),c=CURSOR;
 while(c-->0 && s[at]){int n=span(s,at);x+=n==2?18:16;at+=n;}
 u32 obj=WORD(p,0x1528);if(!obj)return;
 WORD(obj,4)=floatint(x);WORD(obj,8)=floatint(WORD(p,0x1518));
 u32 vt=WORD(obj,0);
 ((void(*)(u32,int))WORD(vt,0x44))(obj,8);
 ((void(*)(u32,int))WORD(vt,0x44))(obj,16);
 ((void(*)(u32,int))WORD(vt,0x14))(obj,0);
 cursor_fx(obj,1000,96,192);
 /* Original frame tail (0x5e1a68..): cursor colour globals and per-letter
    animations. Letters flagged at +0x1534 must count to 0x28 and be released,
    preserving the original animation lifecycle. The erase crash itself was
    caused by O32 stack frames aligned to 8 instead of the EE-required 16. */
 int keep=WORD(p,0x151c);
 ((void(*)(int,int,int))0x5e1130)(0x30,0x90,4);
 ((void(*)(int,int,int))0x5e1130)(0x1c,0x3e,1);
 ((void(*)(int,int,int))0x5e1130)(0x30,0x90,4);
 WORD(p,0x151c)=keep;
 for(int i=0;i<12;i++){
  u8 *b=(u8 *)p+i*16;u32 o=WORD(b,0x153c);
  if(!WORD(b,0x1534) || !o)continue;
  int c=WORD(b,0x1538);
  if(c<0x28){WORD(b,0x1538)=c+1;((void(*)(u32,void*))0x5e1060)(o,b+0x1530);((void(*)(u32,int))WORD(WORD(o,0),0x14))(o,0);}
  if(WORD(b,0x1538)==0x28){WORD(b,0x1538)=0x29;WORD(b,0x1534)=0;((void(*)(u32,int))WORD(WORD(o,0),0x14))(o,0);}
 }
}
/* Use a wrapper for the one five-register engine call; see hooks.S. */
static int replace(void *p,int at,int old,u16 code) {
 u8 *s=(u8 *)p+0x1500;int len=bytes(s),n=code>255?2:1,cap=WORD(p,0x150c);
 if(cap>11)cap=11;
 if(!code || at<0 || at>len || len-old+n>cap)return 0;
 if(n>old)for(int i=len;i>=at+old;i--)s[i+n-old]=s[i];
 else if(n<old)for(int i=at+old;i<=len;i++)s[i+n-old]=s[i];
 s[at]=n==2?code>>8:code;if(n==2)s[at+1]=code;
 return 1;
}
static int syllable(int l,int v,int t){return v<0?initials[l]:0xac00+(l*21+v)*28+t;}
static int set_pending(void *p,int l,int v,int t){
 u16 code=encoded(syllable(l,v,t));if(!code || !replace(p,pending,2,code))return 0;
 if(history_n<8){history_l[history_n]=initial;history_v[history_n]=vowel;history_t[history_n]=final;history_n++;}
 initial=l;vowel=v;final=t;return 1;
}
static int start(void *p,int l,int v,u16 raw){
 u8 *s=(u8*)p+0x1500;int at=offset(s,CURSOR);u16 code=raw?raw:encoded(syllable(l,v,0));
 if(!replace(p,at,0,code))return 0;
 commit();if(!raw){initial=l;vowel=v;pending=at;}CURSOR++;return 1;
}
static int join_vowel(int a,int b){
 if(a==8){if(b==0)return 9;if(b==1)return 10;if(b==20)return 11;}
 if(a==9 && b==20)return 10;
 if(a==13){if(b==4)return 14;if(b==5)return 15;if(b==20)return 16;}
 if(a==14 && b==20)return 15;
 if(a==18 && b==20)return 19;
 if(b==20){if(a==0)return 1;if(a==2)return 3;if(a==4)return 5;if(a==6)return 7;}
 return -1;
}
static int join_final(int a,int b){
 /* Repeated final consonants start a new syllable. Double finals are
    available directly as ㄲ/ㅆ keys, not by consuming the next initial. */
 for(int i=1;i<28;i++)if(i!=2 && i!=20 && split1[i]==a && split2[i]==b)return i;
 return 0;
}
int input(void *p,unsigned key){
 ensure(p);int save_l=initial,save_v=vowel,save_t=final,save_p=pending,save_h=history_n;u16 u=unicode(key);int ok=0;
 if(!u){unsigned c=key>>8;if(c && c<128){commit();ok=start(p,0,0,c);}goto done;}
 int l=indexof(initials,19,u),t=indexof(finals,28,u),v=(u>=0x314f && u<=0x3163)?u-0x314f:-1;
 if(pending<0){if(l>=0)ok=start(p,l,-1,0);else if(v>=0){commit();ok=start(p,0,0,key);}goto done;}
 if(v>=0){
  if(vowel<0){ok=set_pending(p,initial,v,0);goto done;}
  if(final){
   int remain=split1[final],moving=split2[final];
   if(final==2 || final==20){remain=0;moving=final;}
   int nl=indexof(initials,19,finals[moving]);
   u16 left=encoded(syllable(initial,vowel,remain)),right=nl>=0?encoded(syllable(nl,v,0)):0;
   u8 *s=(u8*)p+0x1500;int cap=WORD(p,0x150c);if(cap>11)cap=11;
   if(left && right && bytes(s)+2<=cap){
    replace(p,pending,2,left);ok=start(p,nl,v,0);
   }
  }else{
   int nv=join_vowel(vowel,v);
   if(nv>=0)ok=set_pending(p,initial,nv,0);
   else {commit();ok=start(p,0,0,key);}
  }
 }else if(l>=0 || t>0){
  if(vowel<0){
   int nl=-1;if(l==initial){if(l==0)nl=1;if(l==3)nl=4;if(l==7)nl=8;if(l==9)nl=10;if(l==12)nl=13;}
   if(nl>=0)ok=set_pending(p,nl,-1,0);
   else if(l>=0){commit();ok=start(p,l,-1,0);}
  }else if(!final && t>0){ok=set_pending(p,initial,vowel,t);if(!ok && l>=0)ok=start(p,l,-1,0);}
  else{
   int nt=t>0?join_final(final,t):0;
   if(nt)ok=set_pending(p,initial,vowel,nt);
   if(!ok && l>=0)ok=start(p,l,-1,0);
  }
 }
done: if(ok)refresh(p);else {initial=save_l;vowel=save_v;final=save_t;pending=save_p;history_n=save_h;}sound(!ok);return ok;
}
int erase(void *p){
 ensure(p);u8 *s=(u8*)p+0x1500;
 if(pending>=0){
  if(history_n>0){
   int n=history_n-1,l=history_l[n],v=history_v[n],t=history_t[n];
   if(replace(p,pending,2,encoded(syllable(l,v,t)))){
    initial=l;vowel=v;final=t;history_n=n;refresh(p);return 1;
   }
  }else if(vowel>=0){
   if(replace(p,pending,2,encoded(initials[initial]))){vowel=-1;final=0;refresh(p);return 1;}
  }
 }
 commit();if(CURSOR<=0)return 0;
 int at=offset(s,CURSOR-1),n=span(s,at),len=bytes(s);
 for(int i=at+n;i<=len;i++)s[i-n]=s[i];CURSOR--;refresh(p);return 1;
}
int left(void *p){ensure(p);commit();if(CURSOR>0)CURSOR--;return 1;}
int right(void *p){ensure(p);commit();if(CURSOR<nchars((u8*)p+0x1500))CURSOR++;return 1;}
const u8 *keylabel(unsigned mode,unsigned x,unsigned y){
 if(mode>1 || x>=11 || y>=9)return keytext[0][98];
 return keytext[mode][y*11+x];
}
