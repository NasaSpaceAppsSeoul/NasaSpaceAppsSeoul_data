"""CONAF 개별 산불(모든 크기, 시즌별 |구분 CSV) → inputs/official/CHL/chl_conaf_fires_allsizes_2002_2020.csv (감지율용)
사용: python tools/data_prep/build_chl_perfire.py <CONAF data 폴더>"""
import json, os, pandas as pd, numpy as np
from pathlib import Path as _P
import sys as _sys
ROOT = _P(__file__).resolve().parents[2]                       # 저장소 루트
RAW = _P(_sys.argv[1]) if len(_sys.argv) > 1 else _P("raw")   # 원본 다운로드 폴더 (첫 인자)
OUT = ROOT / "inputs" / "official" / "CHL"
OUT.mkdir(parents=True, exist_ok=True)

D=str(RAW)+'/'
parts=[]
for s in ['20022003','20032004','20042005','20192020']:
    x=pd.read_csv(D+f'{s}/{s}.csv',sep='|'); x['source_file']=f'{s}.csv'; parts.append(x)
g=json.load(open(D+'20182019/20182019.geojson',encoding='utf-8'))
rows=[]
for f in g['features']:
    p=dict(f['properties']); lon,lat=f['geometry']['coordinates'][:2]
    p.setdefault('Latitud',lat); p.setdefault('Longitud',lon); p['_glat'],p['_glon']=lat,lon; rows.append(p)
y=pd.DataFrame(rows); y['source_file']='20182019.geojson'
print('2018-19 geometry vs property max diff:', float(np.nanmax(np.abs(y.Latitud-y._glat))), float(np.nanmax(np.abs(y.Longitud-y._glon))))
parts.append(y.drop(columns=['_glat','_glon']))
a=pd.concat(parts,ignore_index=True)
print('Datum:',a.Datum.value_counts(dropna=False).to_dict())
out=pd.DataFrame({'date':pd.to_datetime(a.Fecha,errors='coerce').dt.strftime('%Y-%m-%d'),'start_time':a['Hora inicio'],
 'lat':pd.to_numeric(a.Latitud,errors='coerce'),'lon':pd.to_numeric(a.Longitud,errors='coerce'),
 'cause':a.Causa,'area_ha':pd.to_numeric(a['Superficie quemada total [ha]'],errors='coerce'),
 'place':a.Nombre.astype(str)+' ('+a.Comuna.astype(str)+')','region':a['Región'],'provincia':a.Provincia,'comuna':a.Comuna,
 'season':a.Temporada,'duration_min':a['Duración (minutos)'],'alert':a.Alerta,'scenario':a.Escenario,'datum':a.Datum,'source_file':a.source_file})
bad=out.lat.isna()|out.lon.isna()|~out.lat.between(-56.5,-17)|~out.lon.between(-110,-66)
print('rows',len(out),'bad coords',int(bad.sum()),'missing date',int(out.date.isna().sum()))
print(out.groupby('season').agg(n=('date','size'),start=('date','min'),end=('date','max'),ha=('area_ha','sum')).round(0))
print('size bins 2018-07+:', pd.cut(out[out.date>='2018-04-01'].area_ha,[-1,0.1,1,10,100,1e9]).value_counts().sort_index().to_dict())
out.to_csv(OUT/'chl_conaf_fires_allsizes_2002_2020.csv',index=False,encoding='utf-8')
