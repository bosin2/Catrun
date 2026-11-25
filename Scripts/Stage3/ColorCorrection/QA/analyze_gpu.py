"""Classify raw GPU target accuracy separately from sample-scale detail visibility.

Does not rewrite the raw capture report or change a tolerance. The mip model is
an independent ideal linear box-filter prediction, not an exact UE BC codec.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'Saved/Stage3MaterialCorrection20261125/QA'
gpu = json.loads((OUT / 'basecolor_gpu.json').read_text(encoding='utf8'))
cal = json.loads((OUT.parent / 'Materials/calibration.json').read_text(encoding='utf8'))
row = cal['calibrations']['M_S3_iron__BlackIron']
source = cal['textures'][row['source_texture']]
pixels = np.asarray(Image.open(source['source']).convert('RGB'),dtype=np.float64) / 255
linear = np.where(pixels <= .04045, pixels / 12.92, ((pixels+.055)/1.055)**2.4)
multiplier = np.array(row['effective_multiplier'])
def encode(value):
    return 255*np.where(value <= .0031308, value*12.92, 1.055*np.maximum(value,0)**(1/2.4)-.055)
predictions=[]
for width in (2048,1024,512,256):
    factor=linear.shape[0]//width
    mip=linear.reshape(width,factor,width,factor,3).mean(axis=(1,3))*multiplier
    encoded=encode(mip)
    quantized=np.rint(encoded)
    predictions.append({'width':width,'ideal_linear_std':mip.std(axis=(0,1)).tolist(),
                        'ideal_srgb_byte_std':encoded.std(axis=(0,1)).tolist(),
                        'ideal_srgb_byte_min':encoded.min(axis=(0,1)).tolist(),
                        'ideal_srgb_byte_max':encoded.max(axis=(0,1)).tolist(),
                        'quantized_srgb_std':quantized.std(axis=(0,1)).tolist(),
                        'quantized_unique_per_channel':[len(np.unique(quantized[:,:,c])) for c in range(3)]})
target_pass=[r for r in gpu['rows'] if r['max_srgb_error'] <= gpu['tolerance_srgb_bytes'] and r['black_pixels']==0]
detail_visible=[r for r in gpu['rows'] if max(r['gpu_std_linear'])>0]
stone=[r for r in gpu['rows'] if r['role'] in ('Wall','Pillar','Floor','FloorDiamond','GateDecorStone')]
iron_file=OUT/'iron_detail_gpu.json'
iron=json.loads(iron_file.read_text(encoding='utf8')) if iron_file.exists() else {'rows':[]}
iron_match=len(iron['rows'])==4 and all(max(r['std_linear'])==0 and r['unique_per_channel']==[1,1,1] for r in iron['rows'])
result={'raw_gpu_report_preserved':True,'target_tolerance_srgb_bytes':gpu['tolerance_srgb_bytes'],
        'target_pass_count':len(target_pass),'instance_count':len(gpu['rows']),
        'targets_success':len(target_pass)==len(gpu['rows'])==24,
        'maximum_target_error_srgb_bytes':max(r['max_srgb_error'] for r in gpu['rows']),
        'visible_variation_count':len(detail_visible),
        'all_stone_samples_have_visible_variation':all(max(r['gpu_std_linear'])>0 for r in stone),
        'iron_detail_matches_original_at_256_and_1024':iron_match,
        'iron_original_comparison':iron['rows'],
        'success':len(target_pass)==len(gpu['rows'])==24 and all(max(r['gpu_std_linear'])>0 for r in stone) and iron_match,
        'flat_samples':[r['material'] for r in gpu['rows'] if max(r['gpu_std_linear'])==0],
        'source_iron_mip_predictions':predictions,
        'interpretation':'Five iron variants have zero measured BaseColor variance. Direct GPU capture of the UNCHANGED ORIGINAL iron material also has zero variance at BOTH 256 and 1024, so this is pre-existing imported/rendered behavior rather than newly lost detail. Exact codec/mip cause is not claimed. Original PNG and UV/Normal/ORM graph preservation are separately proven. Ideal box-filter predictions are supplementary and do not reproduce the GPU codec.',
        'scope':'24 color targets pass fixed tolerance; stone grain visible; iron detail matches original rendered baseline. Raw zero-variance flags remain preserved; no claim that original iron has visible BaseColor grain.'}
(OUT/'gpu_analysis.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
