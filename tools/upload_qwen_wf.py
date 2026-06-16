import paramiko, time, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('connect.nmb1.seetacloud.com', port=21523, username='root', password='kucg0hnB6AmI', timeout=10)

wf = {
  'last_node_id': 20, 'last_link_id': 35, 'version': 0.4,
  'nodes': [
    {'id':1,'type':'NunchakuQwenImageDiTLoader','pos':[50,400],'size':[315,180],'flags':{},'order':0,'mode':0,
     'inputs':[],'outputs':[{'name':'MODEL','type':'MODEL','links':[10]}],
     'widgets_values':['svdq-int4_r128-qwen-image-lightningv1.1-8steps.safetensors','auto',1,'disable'],
     'properties':{'Node name for S&R':'NunchakuQwenImageDiTLoader'}},

    {'id':2,'type':'CLIPLoader','pos':[50,100],'size':[315,82],'flags':{},'order':1,'mode':0,
     'inputs':[],'outputs':[{'name':'CLIP','type':'CLIP','links':[11]}],
     'widgets_values':['qwen_2.5_vl_7b_fp8_scaled.safetensors','qwen_image'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'CLIPLoader'}},

    {'id':3,'type':'VAELoader','pos':[50,600],'size':[315,58],'flags':{},'order':2,'mode':0,
     'inputs':[],'outputs':[{'name':'VAE','type':'VAE','links':[12]}],
     'widgets_values':['qwen_image_vae.safetensors'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'VAELoader'}},

    {'id':4,'type':'CLIPTextEncode','pos':[420,100],'size':[420,180],'flags':{},'order':3,'mode':0,
     'inputs':[{'name':'clip','type':'CLIP','link':11}],
     'outputs':[{'name':'CONDITIONING','type':'CONDITIONING','links':[13]}],
     'widgets_values':['a cute cat sitting on a cloud, anime style'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'CLIPTextEncode (Prompt)'}},

    {'id':5,'type':'EmptySD3LatentImage','pos':[420,320],'size':[315,126],'flags':{},'order':4,'mode':0,
     'inputs':[],'outputs':[{'name':'LATENT','type':'LATENT','links':[14]}],
     'widgets_values':[1024,1024,1],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'EmptySD3LatentImage'}},

    {'id':6,'type':'RandomNoise','pos':[420,480],'size':[315,82],'flags':{},'order':5,'mode':0,
     'inputs':[],'outputs':[{'name':'NOISE','type':'NOISE','links':[15]}],
     'widgets_values':[42,'fixed'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'RandomNoise'}},

    {'id':7,'type':'FluxGuidance','pos':[780,100],'size':[315,58],'flags':{},'order':6,'mode':0,
     'inputs':[{'name':'conditioning','type':'CONDITIONING','link':13}],
     'outputs':[{'name':'CONDITIONING','type':'CONDITIONING','links':[16]}],
     'widgets_values':[3.5],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'FluxGuidance'}},

    {'id':8,'type':'BasicGuider','pos':[780,200],'size':[220,46],'flags':{},'order':7,'mode':0,
     'inputs':[{'name':'model','type':'MODEL','link':10},{'name':'conditioning','type':'CONDITIONING','link':16}],
     'outputs':[{'name':'GUIDER','type':'GUIDER','links':[17]}],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'BasicGuider'}},

    {'id':9,'type':'KSamplerSelect','pos':[780,580],'size':[315,58],'flags':{},'order':8,'mode':0,
     'inputs':[],'outputs':[{'name':'SAMPLER','type':'SAMPLER','links':[18]}],
     'widgets_values':['euler'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'KSamplerSelect'}},

    {'id':10,'type':'BasicScheduler','pos':[780,480],'size':[315,82],'flags':{},'order':9,'mode':0,
     'inputs':[{'name':'model','type':'MODEL','link':10}],
     'outputs':[{'name':'SIGMAS','type':'SIGMAS','links':[19]}],
     'widgets_values':['simple',4,1],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'BasicScheduler'}},

    {'id':11,'type':'SamplerCustomAdvanced','pos':[780,300],'size':[270,124],'flags':{},'order':10,'mode':0,
     'inputs':[{'name':'noise','type':'NOISE','link':15},{'name':'guider','type':'GUIDER','link':17},
               {'name':'sampler','type':'SAMPLER','link':18},{'name':'sigmas','type':'SIGMAS','link':19},
               {'name':'latent_image','type':'LATENT','link':14}],
     'outputs':[{'name':'output','type':'LATENT','links':[20]}],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'SamplerCustomAdvanced'}},

    {'id':12,'type':'VAEDecode','pos':[1100,350],'size':[210,46],'flags':{},'order':11,'mode':0,
     'inputs':[{'name':'samples','type':'LATENT','link':20},{'name':'vae','type':'VAE','link':12}],
     'outputs':[{'name':'IMAGE','type':'IMAGE','links':[21]}],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24','Node name for S&R':'VAEDecode'}},

    {'id':13,'type':'SaveImage','pos':[1100,100],'size':[315,220],'flags':{},'order':12,'mode':0,
     'inputs':[{'name':'images','type':'IMAGE','link':21}],'outputs':[],
     'widgets_values':['ComfyUI'],
     'properties':{'cnr_id':'comfy-core','ver':'0.3.24'}},
  ],
  'links':[
    [10,1,0,8,0,'MODEL'],[10,1,0,10,0,'MODEL'],[11,2,0,4,0,'CLIP'],
    [12,3,0,12,1,'VAE'],[13,4,0,7,0,'CONDITIONING'],[14,5,0,11,4,'LATENT'],
    [15,6,0,11,0,'NOISE'],[16,7,0,8,1,'CONDITIONING'],[17,8,0,11,1,'GUIDER'],
    [18,9,0,11,2,'SAMPLER'],[19,10,0,11,3,'SIGMAS'],[20,11,0,12,0,'LATENT'],
    [21,12,0,13,0,'IMAGE']
  ],
  'groups':[],'config':{},'extra':{}
}

json_str = json.dumps(wf, indent=2)
stdin, stdout, stderr = c.exec_command('cat > /root/autodl-tmp/ComfyUI/user/default/workflows/qwen_v2.json')
stdin.write(json_str); stdin.close()
time.sleep(1)
print('Uploaded qwen_v2.json')
c.close()
