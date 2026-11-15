"""NPWS 화재 이력을 ArcGIS 서버에서 직접 받아 → inputs/official/NSW/nsw_npws_wildfires_2000_2026.csv (인자 필요 없음)
사용: python tools/data_prep/build_nsw.py"""
import json,urllib.request,urllib.parse,numpy as np,pandas as pd,datetime,time
from matplotlib.path import Path as MP
from pathlib import Path as _P
import sys as _sys
ROOT = _P(__file__).resolve().parents[2]                       # 저장소 루트
RAW = _P(_sys.argv[1]) if len(_sys.argv) > 1 else _P("raw")   # 원본 다운로드 폴더 (첫 인자)
OUT = ROOT / "inputs" / "official" / "NSW"
OUT.mkdir(parents=True, exist_ok=True)

B='https://mapprod3.environment.nsw.gov.au/arcgis/rest/services/Fire/NPWS_Fire_History/MapServer/0/query'
rows=[];off=0
while True:
    q=dict(where='FireType=1 AND FireYear>=200001',outFields='OBJECTID,FireName,FireNo,FireYear,StartDate,EndDate,AreaHa,NPWSBranch,NPWSArea,VerDate',
           returnGeometry='true',outSR='4326',maxAllowableOffset='0.002',orderByFields='OBJECTID',resultOffset=str(off),resultRecordCount='1000',f='json')
    d=json.load(urllib.request.urlopen(B+'?'+urllib.parse.urlencode(q),timeout=180))
    fs=d.get('features',[])
    for f in fs:
        a=f['attributes']; rings=(f.get('geometry') or {}).get('rings') or []
        lon=lat=None
        if rings:
            # largest ring by |area|; area-weighted centroid; keep inside ring
            def area(r): r=np.asarray(r); x,y=r[:,0],r[:,1]; return 0.5*(x[:-1]*y[1:]-x[1:]*y[:-1]).sum()
            r=np.asarray(max(rings,key=lambda r:abs(area(r)))); A=area(r); x,y=r[:,0],r[:,1]; c=x[:-1]*y[1:]-x[1:]*y[:-1]
            (cx,cy)=(((x[:-1]+x[1:])*c).sum()/(6*A),((y[:-1]+y[1:])*c).sum()/(6*A)) if abs(A)>1e-12 else tuple(r[:-1].mean(0))
            P=MP(r)
            if abs(A)>1e-12 and not P.contains_point((float(cx),float(cy))):
                gx,gy=np.meshgrid(np.linspace(x.min(),x.max(),30),np.linspace(y.min(),y.max(),30)); g=np.c_[gx.ravel(),gy.ravel()]; g=g[P.contains_points(g)]
                if len(g): cx,cy=g[np.argmin(((g-[cx,cy])**2).sum(1))]
            lon,lat=round(float(cx),5),round(float(cy),5)
        t=lambda v: datetime.datetime.fromtimestamp(v/1000,datetime.timezone.utc).date() if v else None
        rows.append(dict(date=t(a['StartDate']),end_date=t(a['EndDate']),fire_year=a['FireYear'],lat=lat,lon=lon,area_ha=a['AreaHa'],cause='',
                         place=(a['FireName'] or '').strip(),fire_no=a['FireNo'],npws_area=a['NPWSArea'],objectid=a['OBJECTID'],ver_date=t(a['VerDate'])))
    off+=len(fs)
    if not d.get('exceededTransferLimit') or not fs: break
    time.sleep(0.5)
df=pd.DataFrame(rows).sort_values(['date','objectid'],na_position='first')
df.to_csv(OUT/'nsw_npws_wildfires_2000_2026.csv',index=False)
print('wildfires',len(df),'with date',df.date.notna().sum(),'with point',df.lat.notna().sum(),'dates',df.date.min(),'→',df.date.max(),'latest ver',df.ver_date.max())
df['y']=pd.to_datetime(df.date).dt.year
print(df.groupby('y').agg(n=('objectid','size'),ha=('area_ha','sum')).round(0).astype(int).T.to_string())
print('fire_year rows without date by season:',df[df.date.isna()].fire_year.value_counts().sort_index().to_dict())
