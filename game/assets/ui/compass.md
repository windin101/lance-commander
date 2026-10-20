# compass.png

The original's ground compass texture, converted unchanged (RGBA, 256 x 256) from the Shared Source
release: `reference/mc2-source/Source/Data/TGL/128/A_Compass.tga` (used by `Data/TGL/Compass.ase`, the
"compass" building appearance drawn at the camera focus, `Code/gamecam.cpp:557-596`). Shared Source art:
non-commercial use only, under the release's EULA (`docs/MC2-SOURCE-EULA.md`). Its alpha tops out at
77/255 (~30%), which is the decal's translucency; `CameraCompass` uses it as is.

Regenerate: `python3 -c "from PIL import Image; Image.open('reference/mc2-source/Source/Data/TGL/128/A_Compass.tga').save('game/assets/ui/compass.png')"`
