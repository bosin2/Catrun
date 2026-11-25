import unreal as u
for n in ['LocalFogVolume','LocalFogVolumeComponent','ExponentialHeightFogComponent','TriggerBox','LightingChannels','MaterialExpressionSine','CineCameraActor']:
    c=getattr(u,n,None);print(n,str(c));print(c.__doc__[:4500] if c else '')
