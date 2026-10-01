# scanEar

Interfaz para escáner 3D: control por puerto serial, captura de cámara y procesamiento de mallas.

## Estructura

- `main.py` — interfaz principal del escáner (Tkinter, serial, OpenCV).
- `3d_mod/main.py` — visor/editor de modelos 3D (PySide6, vedo, VTK).
- `back/main.py` — versión anterior de la interfaz del escáner.

## Dependencias

```bash
pip install pyserial opencv-python numpy pillow piexif PySide6 vedo vtk
```

## Uso

```bash
python main.py          # escáner
python 3d_mod/main.py   # modelos 3D
```

## Licencia

[MIT](LICENSE)
