"""Serialize new native measurements; never mutate the historical publication."""
import json
import math
import shlex
from pathlib import Path


def rows(manifest,baseline_adapter='bgzip'):
    names=[a['plan']['codec'] for a in manifest['adapters']]
    if len(names)!=len(set(names)):
        raise ValueError('duplicate codec labels cannot identify a unique baseline')
    result=[]
    baseline=next((a['plan']['codec'] for a in manifest['adapters'] if Path(a['plan']['adapter']).stem==baseline_adapter),None)
    for adapter in manifest['adapters']:
        plan=adapter['plan'];cfg=plan['configuration']
        common={'codec':plan['codec'],'version':plan['version'],'corpus':manifest['corpus'],
            'corpus_md5':manifest['corpus_md5'],'granularity':cfg['granularity'],
            'configuration':cfg,'run_id':manifest['run_id'],'host':manifest['host'],
            'toolchain':{'compiler':manifest['compiler'],'qualified_dependency_receipt':plan['qualification_sha256']},
            'qualification_sha256':plan['qualification_sha256']}
        def emit(axis,value,unit,source=None,level='declared',**extra):
            source=source or {}
            command=source.get('command') or source.get('compress_command') or shlex.join([
                './run.sh','--measure','--codec',plan['adapter'],'--axis',axis.split(':')[0],
                '--input',manifest['corpus'],'--work',str(Path(plan['work']).parent),'--output-dir','NEW_RUN_DIRECTORY'])
            record=dict(common,axis=axis,value=value,unit=unit,level=level,command=command,
                verified=source.get('verified','n/a'),n_samples=source.get('n_samples',1 if source.get('verified')=='byte-exact' else 0),
                status='measured' if value is not None else 'n/a',**extra)
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
                raise ValueError('invalid serialized measurement')
            if value is None and not record.get('reason'):raise ValueError('n/a requires a reason')
            record['configuration']=source.get('configuration',cfg)
            if 'point_granularity' in extra:record['granularity']=extra['point_granularity']
            result.append(record)
        for item in adapter['measurements']:
            axis=item['axis'];value=item['value']
            if value is None:
                for g in ((4096,16384,65536,262144,1048576) if axis=='c_g' else (cfg['granularity'],)):
                    emit(axis,None,'n/a',reason=item['reason'],point_granularity=g)
                continue
            if axis=='ratio':emit(axis,value['ratio'],'input_bytes/stored_bytes',value,level='reproducible')
            elif axis=='region':
                for p in ('p50','p99'):emit('region:'+p,value['region_'+p+'_ms'],'ms',value)
            elif axis=='amplification':emit(axis,value['value'],'decoded_bytes/returned_bytes',value,level='reproducible')
            elif axis=='break_even':emit(axis,value['break_even_N'],'requests',value)
            elif axis in ('encode','decode'):
                if 'points' not in value:
                    emit('decode:sample',value['sample_MB_s'],'MB/s',value,plateau_status='data_edge')
                else:
                    for point in value['points']:
                        p=dict(point,n_samples=len(point['sample_wall_ms']),command=point.get('command') or point['commands'][0])
                        emit(axis+':curve',point['value'],'MB/s',p,copies=point['copies'])
                    emit(axis,value['value'],'MB/s',dict(value['points'][-1],command=value['points'][-1].get('command') or value['points'][-1]['commands'][0],n_samples=len(value['points'][-1]['sample_wall_ms'])),reason=value['reason'],plateau_status=value['status'])
            elif axis=='h_alpha':
                for p in value['profiles']:
                    emit(axis,p['H_alpha_bits'],'bits',{'n_samples':p['count']},level='reproducible',profile=p['profile'],ranges=p['count'])
            elif axis=='batch':
                for p in value['profiles']:
                    for method in ('loop','batch'):
                        emit(axis+':'+method,p[method+'_ranges_s'],'ranges/s',p,profile=p['profile'],ranges=p['count'],threads=1)
            elif axis=='c_g':
                for p in value['points']:
                    emit(axis,p['c_g_percent'],'percent',p,level='reproducible',point_granularity=p['granularity'],
                         baseline_archive_bytes=value['baseline']['archive_bytes'],geometry=p['geometry'])
            else:raise ValueError('unserialized axis: '+axis)
    def key(r):return tuple(r.get(k) for k in ('axis','profile','ranges','copies','point_granularity'))
    bases={key(r):r for r in result if r['codec']==baseline}
    for row in result:
        b=bases.get(key(row))
        available=row['value'] is not None and b is not None and b['value'] not in (None,0)
        row['baseline_ratio']={'vs':baseline or baseline_adapter,'value':row['value']/b['value'] if available else None,
            'orientation':'codec_value / baseline_value',
            'reason':None if available else 'no nonzero comparable baseline measurement in this run'}
    return result
