"""그리스 소방청 연도별 xlsx(greece_fire_service_2000-2024.zip을 푼 폴더) → inputs/official/GRC/grc_fire_service_2000_2024.csv
사용: python tools/data_prep/build_grc.py <푼 폴더>"""
import openpyxl,glob,datetime,numpy as np,pandas as pd,re
from pathlib import Path as _P
import sys as _sys
ROOT = _P(__file__).resolve().parents[2]                       # 저장소 루트
RAW = _P(_sys.argv[1]) if len(_sys.argv) > 1 else _P("raw")   # 원본 다운로드 폴더 (첫 인자)
OUT = ROOT / "inputs" / "official" / "GRC"
OUT.mkdir(parents=True, exist_ok=True)

D=str(RAW)+'/'
AREA=['Δάση','Δασική Έκταση','Άλση','Χορτ/κές Εκτάσεις','Καλάμια - Βάλτοι','Γεωργικές Εκτάσεις','Υπολλείματα Καλλιεργειών']
def norm(s): return re.sub(r'\s+',' ',str(s or '').strip())
rows=[]
def sheet_rows(ws):
    it=ws.iter_rows(values_only=True); hdr=None
    for r in it:
        if hdr is None:
            if r and any(isinstance(c,str) and 'Έναρξης' in c for c in r): hdr=[norm(c) for c in r]
            continue
        yield hdr,r
def xy_sheet(wb):
    for n in wb.sheetnames:
        if n.lower().startswith('engage'):
            ws=wb[n]; it=ws.iter_rows(values_only=True); h=[norm(c).upper() for c in next(it)]
            iu,ilo,ila=h.index('INCIDENT_UID'),h.index('LONGITUDE'),h.index('LATITUDE')
            return {r[iu]:(r[ilo],r[ila]) for r in it if r and r[iu] is not None}
    return {}
files=sorted(glob.glob(D+'Dasikes_Pyrkagies_*.xlsx'))
for f in files:
    wb=openpyxl.load_workbook(f,read_only=True,data_only=True); XY=xy_sheet(wb)
    sheets=[wb[s] for s in wb.sheetnames if re.fullmatch(r'\d{4}',s)] or [wb.worksheets[0]]
    for ws in sheets:
        for h,r in sheet_rows(ws):
            g=lambda name: r[h.index(name)] if name in h and h.index(name)<len(r) else None
            d=g('Ημερ/νία Έναρξης')
            if not isinstance(d,(datetime.datetime,datetime.date)): continue
            areas=[]; 
            for a in AREA:
                k=[i for i,c in enumerate(h) if c.replace('-','').replace(' ','')==a.replace('-','').replace(' ','')]
                if k and isinstance(r[k[0]],(int,float)): areas.append(r[k[0]])
            sk=[i for i,c in enumerate(h) if c.startswith('Σκουπι')]
            if sk and isinstance(r[sk[0]],(int,float)): areas.append(r[sk[0]])
            lon=lat=None
            if 'X-ENGAGE' in h:
                x,y=g('X-ENGAGE'),g('Y-ENGAGE')
                if isinstance(x,(int,float)) and isinstance(y,(int,float)): lon,lat=x,y
                elif XY and g('Α/Α ENGAGE') in XY: lon,lat=XY[g('Α/Α ENGAGE')]
            place=' / '.join(p for p in [norm(g('Περιοχή') or g('Περιοχή - Τοποθεσία')),norm(g('Διεύθυνση'))] if p and p!='-')
            dimos=norm(g('Δήμος')); dimos='' if dimos in ('-','') else dimos
            ed=g('Ημερ/νία Κατασβεσης'); ed=pd.Timestamp(ed).date() if isinstance(ed,(datetime.datetime,datetime.date)) else None
            tm=lambda v: v.strftime('%H:%M') if isinstance(v,(datetime.time,datetime.datetime)) else norm(v)
            rows.append(dict(date=pd.Timestamp(d).date(),start_time=tm(g('Ώρα Έναρξης')),end_date=ed,end_time=tm(g('Ώρα Κατάσβεσης')),
                             station=norm(g('Υπηρεσία')),forestry_office=norm(g('Δασαρχείο')),record_id=g('Α/Α ΕΓΓΡΑΦΗΣ'),engage_id=g('Α/Α ENGAGE'),
                             nomos=norm(g('Νομός')),dimos=dimos,place=place,
                             area_ha=round(sum(areas)/10,4),lon=lon,lat=lat,source_file=f.split('/')[-1]))
df=pd.DataFrame(rows)
for c in ['lon','lat']: df[c]=pd.to_numeric(df[c],errors='coerce')
_dupcols=[c for c in df.columns if c!='source_file']
_dup=df.duplicated(_dupcols)
print('exact duplicate rows in source (same date, times, station, place, areas, ids):',int(_dup.sum()),'by year',df[_dup].groupby(pd.to_datetime(df[_dup].date).dt.year).size().to_dict())
df=df[~_dup].copy()
ok=df.lon.between(19,30)&df.lat.between(34,42.2)
df.loc[~ok,['lon','lat']]=np.nan
df['loc_quality']=np.where(ok,'exact','')
# representative points (medoid of exact points) per dimos and per nomos
ex=df[ok]
def medoid(g):
    a=g[['lon','lat']].to_numpy(); m=np.median(a,0); i=np.argmin(((a-m)**2).sum(1)); return pd.Series({'lon':a[i,0],'lat':a[i,1],'n':len(a)})
dm=ex[ex.dimos!=''].groupby('dimos').apply(medoid); nm=ex.groupby('nomos').apply(medoid)
dm=dm[dm.n>=3]; nm=nm[nm.n>=3]
miss=df.loc_quality==''
md=miss&df.dimos.isin(dm.index)
df.loc[md,['lon','lat']]=dm.loc[df.loc[md,'dimos'],['lon','lat']].to_numpy(); df.loc[md,'loc_quality']='municipality'
mn=(df.loc_quality=='')&df.nomos.isin(nm.index)
df.loc[mn,['lon','lat']]=nm.loc[df.loc[mn,'nomos'],['lon','lat']].to_numpy(); df.loc[mn,'loc_quality']='prefecture'
df['cause']=''
df['year']=pd.to_datetime(df.date).dt.year
df=df.sort_values(['date','start_time'])[['date','start_time','end_date','end_time','year','lat','lon','loc_quality','area_ha','cause','nomos','dimos','place','station','forestry_office','record_id','engage_id','source_file']]
out=OUT/'grc_fire_service_2000_2024.csv'
df.to_csv(out,index=False,encoding='utf-8')
print('rows',len(df),'->',out)
print(pd.crosstab(df.year,df.loc_quality.replace('','none')).to_string())
print('unlocated nomos values:',df[df.loc_quality==''].nomos.value_counts().head(8).to_dict())
