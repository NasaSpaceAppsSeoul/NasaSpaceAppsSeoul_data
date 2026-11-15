"""CONAF 통계 xlsx(대형 산불, 코무나별 시즌 집계) → inputs/official/CHL/ CSV 3개
사용: python tools/data_prep/build_chl.py <CONAF xlsx 폴더>"""
import sys,re,json,unicodedata,datetime,numpy as np,pandas as pd,xlrd,openpyxl
from matplotlib.path import Path as MP
from pathlib import Path as _P
import sys as _sys
ROOT = _P(__file__).resolve().parents[2]                       # 저장소 루트
RAW = _P(_sys.argv[1]) if len(_sys.argv) > 1 else _P("raw")   # 원본 다운로드 폴더 (첫 인자)
OUT = ROOT / "inputs" / "official" / "CHL"
OUT.mkdir(parents=True, exist_ok=True)

def key(s): s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().upper(); return re.sub(r'[^A-Z]','',s)
# comuna representative points from boundary file
B=json.load(open(ROOT/'boundaries/CHL/geoBoundaries-CHL-ADM2.geojson',encoding='utf-8'))['features']
rep={}
for f in B:
    ps=f['geometry']['coordinates']; big=max(ps,key=lambda p:len(p[0])); a=np.asarray(big[0]); P=MP(a)
    x0,y0=a.min(0); x1,y1=a.max(0); gx,gy=np.meshgrid(np.linspace(x0,x1,40),np.linspace(y0,y1,40)); g=np.c_[gx.ravel(),gy.ravel()]; g=g[P.contains_points(g)]
    c=a.mean(0); p=g[np.argmin(((g-c)**2).sum(1))] if len(g) else c
    rep[key(f['properties']['shapeName'])]=(round(float(p[0]),5),round(float(p[1]),5),f['properties']['shapeName'])
ALIAS={'PAIHUANO':'PAIGUANO','TREGUACO':'TREHUACO','LLAYLLAY':'LLAILLAY','MARCHIHUE':'MARCHIGUE','VINADEMAR':'VINADELMAR','FUTALELFU':'FUTALEUFU','GUAYTECAS':'GUAITECAS','JUANFERNADEZ':'JUANFERNANDEZ','VILLARICA':'VILLARRICA','NINQUEN':'NIQUEN','LOMQUIMAY':'LONQUIMAY','PUERTONATALES':'NATALES'}
def loc(com):
    k=key(com); k=ALIAS.get(k,k)
    if k in rep: return rep[k]
    for kk in rep:
        if kk.startswith(k) or k.startswith(kk): return rep[kk]
    return None
MES={'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'sept':9,'oct':10,'nov':11,'dic':12}
def pdate(v,dm):
    if isinstance(v,float) and v>1000: return xlrd.xldate_as_datetime(v,dm).date()
    m=re.match(r'\s*(\d{1,2})-([a-zA-Z]+)-(\d{2,4})',str(v))
    if m:
        y=int(m.group(3)); y=y+2000 if y<100 else y
        mo=MES.get(m.group(2).lower()[:4]) or MES.get(m.group(2).lower()[:3])
        if mo: return datetime.date(y,mo,int(m.group(1)))
    return None
def dms(s):
    m=re.findall(r'(\d+(?:\.\d+)?)',str(s))
    if len(m)<2: return None
    v=float(m[0])+float(m[1])/60+(float(m[2])/3600 if len(m)>2 else 0)
    return -v
# ---- large fires (>=200 ha)
b=xlrd.open_workbook(str(RAW)+'/magnitud.xls'); rows=[]; miss={}
for n in b.sheet_names():
    if not re.fullmatch(r'\d{4}',n): continue
    s=b.sheet_by_name(n); hi=next(i for i in range(s.nrows) if str(s.row_values(i)[0]).strip().upper()=='REGION'); h=[str(c).strip().upper() for c in s.row_values(hi)]
    has_ll='LATITUD' in h; ci=h.index('COMUNA'); ni=next(i for i,c in enumerate(h) if c.startswith('NOMBRE') or (c=='' and i==6))
    di=h.index('FECHA INICIO') if 'FECHA INICIO' in h else 7
    region=prov=''
    for i in range(hi+3,s.nrows):
        r=s.row_values(i)
        if str(r[0]).strip().upper().startswith('TOTAL') or str(r[ci]).strip()=='' : continue
        region=str(r[0]).strip() or region; prov=str(r[1]).strip() or prov
        d=pdate(r[di],b.datemode)
        if d is None: continue
        lat=lon=None; q=''
        if has_ll: lat,lon=dms(r[h.index('LATITUD')]),dms(r[h.index('LONGITUD')]); q='exact' if lat and lon else ''
        com=str(r[ci]).strip()
        if not q:
            L=loc(com)
            if L: lon,lat,_=L; q='comuna'
            else: miss[com]=miss.get(com,0)+1
        tot=r[-1] if isinstance(r[-1],float) else None
        rows.append(dict(date=d,season=f'{int(n)-1}-{n}',lat=lat,lon=lon,loc_quality=q,area_ha=tot,cause='',region=region,provincia=prov,comuna=com,
                         place=str(r[ni]).strip(),agency=str(r[h.index('AMBITO')]).strip()))
big=pd.DataFrame(rows).sort_values('date')
big.to_csv(OUT/'chl_conaf_large_fires_1985_2024.csv',index=False,encoding='utf-8')
print('large fires',len(big),big.date.min(),big.date.max(),dict(big.loc_quality.value_counts()),'unmatched comunas',miss)
print(big.groupby(pd.to_datetime(big.date).dt.year).size().tail(8).to_dict(), 'area>=200 share',(big.area_ha>=200).mean().round(3))
# ---- seasonal counts per comuna
wb=openpyxl.load_workbook(str(RAW)+'/comuna.xlsx',read_only=True,data_only=True); out=[]
for ws in wb.worksheets:
    rws=list(ws.iter_rows(values_only=True)); reg=prov=''
    title=' '.join(str(c) for r in rws[:3] for c in r if c)
    m=re.search(r'(\d{4})\s*-\s*(\d{4})',title) or re.search(r'(\d{2})-(\d{2})',ws.title)
    y0=int(m.group(1)); y0=y0+1900 if y0<100 else y0
    start=next(i for i,r in enumerate(rws) if r and r[0]=='REGION')+3
    for r in rws[start:]:
        if not r or r[2] in (None,'TOTAL') or r[0]=='TOTAL': continue
        reg=r[0] or reg; prov=r[1] or prov
        n=r[3] if isinstance(r[3],(int,float)) else 0
        nums=[c for c in r[4:] if isinstance(c,(int,float))]; a=nums[-1] if nums else 0   # rightmost number = TOTAL SUPERFICIE (column position varies by sheet)
        out.append(dict(season=f'{y0}-{y0+1}',season_start_year=y0,region=reg,provincia=prov,comuna=r[2],n_fires=int(n),area_ha=round(a,2)))
sc=pd.DataFrame(out).sort_values(['season_start_year','region','comuna'])
sc.to_csv(OUT/'chl_conaf_comuna_season_1984_2024.csv',index=False,encoding='utf-8')
nat=sc.groupby(['season','season_start_year']).agg(n_fires=('n_fires','sum'),area_ha=('area_ha','sum')).reset_index()
# cross-check with each sheet's TOTAL NACIONAL row
chk=[]
for ws in wb.worksheets:
    for r in ws.iter_rows(values_only=True):
        if r and r[0]=='TOTAL NACIONAL':
            nums=[c for c in r[4:] if isinstance(c,(int,float))]; chk.append((r[3],nums[-1] if nums else None)); break
print('national rows vs comuna sums (n, area) max diff:', max(abs(a-b) for (a,_),b in zip(chk[::-1],nat.n_fires)) if len(chk)==len(nat) else 'len mismatch')
nat.to_csv(OUT/'chl_conaf_national_season_1984_2024.csv',index=False)
print('season rows',len(sc),'seasons',sc.season.nunique()); print(nat.tail(6).to_string(index=False))
