import sys
import os
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QFileDialog, QLabel, QDoubleSpinBox, QGroupBox,
                              QRadioButton, QButtonGroup, QFrame, QSizePolicy, QSlider)
from PySide6.QtCore import Qt, Signal, Slot
from vedo import Mesh, show, settings, Tube, Box, Plotter, Line, Point, Cylinder, vector
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkFiltersGeneral import vtkBooleanOperationPolyDataFilter
import vtk

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visor de STL con Editor de Conductos")
        self.resize(1200, 900)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Crear el widget VTK para la visualización
        from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        self.vtk_widget = QVTKRenderWindowInteractor()
        self.vtk_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.vtk_widget)
        
        # Panel de control
        control_layout = QHBoxLayout()
        
        # Grupo de botones para cargar/guardar
        file_group = QGroupBox("Archivo")
        file_layout = QVBoxLayout(file_group)
        
        self.load_button = QPushButton("Cargar STL")
        self.load_button.clicked.connect(self.load_stl)
        file_layout.addWidget(self.load_button)
        
        self.save_button = QPushButton("Guardar STL")
        self.save_button.clicked.connect(self.save_stl)
        self.save_button.setEnabled(False)
        file_layout.addWidget(self.save_button)
        
        control_layout.addWidget(file_group)
        
        # Grupo de botones para navegación
        nav_group = QGroupBox("Navegación")
        nav_layout = QVBoxLayout(nav_group)
        
        self.reset_button = QPushButton("Reiniciar Vista")
        self.reset_button.clicked.connect(self.reset_view)
        nav_layout.addWidget(self.reset_button)
        
        nav_radio_layout = QHBoxLayout()
        self.nav_mode = QRadioButton("Navegar")
        self.nav_mode.setChecked(True)
        self.select_mode = QRadioButton("Seleccionar")
        
        # Agrupar los botones de radio
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.nav_mode, 1)
        self.mode_group.addButton(self.select_mode, 2)
        self.mode_group.buttonClicked.connect(self.mode_changed)
        
        nav_radio_layout.addWidget(self.nav_mode)
        nav_radio_layout.addWidget(self.select_mode)
        nav_layout.addLayout(nav_radio_layout)
        
        # Añadir control deslizante para transparencia
        transparency_layout = QHBoxLayout()
        transparency_layout.addWidget(QLabel("Transparencia:"))
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_slider.setRange(0, 100)
        self.transparency_slider.setValue(0)  # 0% transparencia por defecto
        self.transparency_slider.setTickPosition(QSlider.TicksBelow)
        self.transparency_slider.setTickInterval(10)
        self.transparency_slider.valueChanged.connect(self.update_transparency)
        transparency_layout.addWidget(self.transparency_slider)
        nav_layout.addLayout(transparency_layout)
        
        control_layout.addWidget(nav_group)
        
        # Grupo de controles para puntos
        points_group = QGroupBox("Puntos")
        points_layout = QVBoxLayout(points_group)
        
        self.pointA_button = QPushButton("Seleccionar Punto A")
        self.pointA_button.clicked.connect(lambda: self.set_point_selection('A'))
        points_layout.addWidget(self.pointA_button)
        
        self.pointB_button = QPushButton("Seleccionar Punto B")
        self.pointB_button.clicked.connect(lambda: self.set_point_selection('B'))
        points_layout.addWidget(self.pointB_button)
        
        self.clear_points_button = QPushButton("Limpiar Puntos")
        self.clear_points_button.clicked.connect(self.clear_selection)
        points_layout.addWidget(self.clear_points_button)
        
        control_layout.addWidget(points_group)
        
        # Grupo de controles para conducto
        conducto_group = QGroupBox("Conducto")
        conducto_layout = QVBoxLayout(conducto_group)
        
        diam_layout = QHBoxLayout()
        diam_layout.addWidget(QLabel("Diámetro:"))
        self.diameter_spin = QDoubleSpinBox()
        self.diameter_spin.setRange(0.01, 1.0)
        self.diameter_spin.setSingleStep(0.01)
        self.diameter_spin.setValue(0.05)
        self.diameter_spin.valueChanged.connect(self.update_preview)
        diam_layout.addWidget(self.diameter_spin)
        conducto_layout.addLayout(diam_layout)
        
        self.preview_button = QPushButton("Vista Previa")
        self.preview_button.clicked.connect(self.create_preview)
        conducto_layout.addWidget(self.preview_button)
        
        self.apply_button = QPushButton("Aplicar Conducto")
        self.apply_button.clicked.connect(self.apply_conducto)
        self.apply_button.setEnabled(False)
        conducto_layout.addWidget(self.apply_button)
        
        control_layout.addWidget(conducto_group)
        
        # Añadir panel de control al layout principal
        main_layout.addLayout(control_layout)
        
        # Línea separadora
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # Información
        self.info_label = QLabel("Listo para cargar modelo STL")
        main_layout.addWidget(self.info_label)
        
        # Atributos
        self.mesh = None
        self.original_mesh = None  # Para guardar el original
        self.pointA = None
        self.pointB = None
        self.pointA_marker = None
        self.pointB_marker = None
        self.conducto_preview = None
        self.selection_mode = None  # 'A' o 'B' según el punto a seleccionar
        self.plotter = None
        self.alpha_value = 1.0  # Transparencia inicial (opaco)
        
        # Inicializar el render window
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()
        
    def update_transparency(self, value):
        if self.mesh is None:
            return
            
        # Convertir valor del slider (0-100) a alpha (1.0-0.0)
        # Nota: A menor alpha, más transparente
        self.alpha_value = 1.0 - (value / 100.0)
        
        # Aplicar transparencia
        self.mesh.alpha(self.alpha_value)
        
        # Actualizar visualización
        if self.plotter:
            self.plotter.render()
            
        # Mostrar información
        alpha_percent = int((1.0 - self.alpha_value) * 100)
        self.info_label.setText(f"Transparencia: {alpha_percent}%")

    def load_stl(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir STL", "", "STL Files (*.stl)")
        if not file_path:
            return
        
        try:
            # Cargar el modelo y normalizar su posición y tamaño
            self.original_mesh = Mesh(file_path)
            self.mesh = self.original_mesh.clone().normalize()
            self.mesh.color((0.7, 0.7, 0.9))
            
            # Limpiar selección anterior
            self.clear_selection()
            
            # Cerrar plotter anterior si existe
            if self.plotter:
                self.plotter.close()
                
            # Crear nuevo plotter
            self.plotter = Plotter(qt_widget=self.vtk_widget, axes=1, bg="lightgrey")
            
            # Aplicar transparencia actual
            self.mesh.alpha(self.alpha_value)
            
            self.plotter.show(self.mesh)
            
            # Configurar estilo de interacción
            interactor = self.plotter.interactor
            if interactor:
                interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
            
            # Conectar evento de clic solo si estamos en modo selección
            self.plotter.add_callback("mouse click", self.on_mouse_click)
            
            # Agregar caja de vistas
            self.add_view_box()
            
            # Actualizar estado de botones
            self.save_button.setEnabled(True)
            self.nav_mode.setChecked(True)
            self.mode_changed()  # Actualizar modo
            
            self.info_label.setText("Modelo cargado. Seleccione 'Modo Selección' y use los botones para marcar puntos.")
        except Exception as e:
            self.info_label.setText(f"Error al cargar el modelo: {str(e)}")
            print(f"Error al cargar el modelo: {str(e)}")
            import traceback
            traceback.print_exc()

        
    def save_stl(self):
        if self.mesh is None:
            self.info_label.setText("No hay modelo para guardar.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar STL", "", "STL Files (*.stl)")
        if not file_path:
            return
            
        # Asegurarse que tenga la extensión .stl
        if not file_path.lower().endswith('.stl'):
            file_path += '.stl'
            
        try:
            # Crear una copia del mesh para asegurar que se guarde sin transparencia
            save_mesh = self.mesh.clone()
            
            # Obtener los datos de forma compatible
            mesh_data = None
            try:
                mesh_data = save_mesh.dataset
            except:
                try:
                    mesh_data = save_mesh.polydata()
                except:
                    self.info_label.setText("Error: No se pudo acceder a los datos del modelo")
                    return
            
            # Guardar usando vtk directamente
            writer = vtk.vtkSTLWriter()
            writer.SetFileName(file_path)
            writer.SetInputData(mesh_data)
            writer.Write()
            
            self.info_label.setText(f"Modelo guardado en: {file_path}")
                
        except Exception as e:
            self.info_label.setText(f"Error al guardar: {str(e)}")
            print(f"Error al guardar: {str(e)}")
            import traceback
            traceback.print_exc()

    def mode_changed(self):
        # Cambiar el modo de interacción según el radio button seleccionado
        if self.nav_mode.isChecked():
            if self.plotter and self.plotter.interactor:
                self.plotter.interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
                self.selection_mode = None
                self.info_label.setText("Modo navegación activado. Use el ratón para mover la vista.")
                # Deshabilitar botones de selección
                self.pointA_button.setEnabled(False)
                self.pointB_button.setEnabled(False)
        else:  # Modo selección
            if self.plotter and self.plotter.interactor:
                # Mantenemos el mismo interactor pero ahora procesaremos los eventos de clic
                self.info_label.setText("Modo selección activado. Presione 'Seleccionar Punto A' o 'Seleccionar Punto B'.")
                # Habilitar botones de selección
                self.pointA_button.setEnabled(True)
                self.pointB_button.setEnabled(True)
        
    def set_point_selection(self, point_type):
        if not self.select_mode.isChecked():
            self.select_mode.setChecked(True)
            self.mode_changed()
            
        self.selection_mode = point_type
        
        if point_type == 'A':
            self.info_label.setText("Haga clic en el modelo para seleccionar el Punto A.")
        else:
            self.info_label.setText("Haga clic en el modelo para seleccionar el Punto B.")
        
    def on_mouse_click(self, evt):
        # Solo procesar clics si estamos en modo selección y hay un modo de selección activo
        if self.mesh is None or not self.select_mode.isChecked() or not self.selection_mode:
            return
        
        clicked_point = evt.picked3d
        if clicked_point is None:
            return
            
        # Procesamos según si queremos seleccionar A o B
        if self.selection_mode == 'A':
            # Eliminar marcador anterior del punto A si existe
            if self.pointA_marker is not None:
                self.plotter.remove(self.pointA_marker)
                
            # Guardar nuevo punto A y crear marcador
            self.pointA = clicked_point
            self.pointA_marker = Point(clicked_point, c="red", r=12).legend('A')
            self.plotter.add(self.pointA_marker)
            self.info_label.setText("Punto A seleccionado.")
            
        elif self.selection_mode == 'B':
            # Eliminar marcador anterior del punto B si existe
            if self.pointB_marker is not None:
                self.plotter.remove(self.pointB_marker)
                
            # Guardar nuevo punto B y crear marcador
            self.pointB = clicked_point
            self.pointB_marker = Point(clicked_point, c="blue", r=12).legend('B')
            self.plotter.add(self.pointB_marker)
            self.info_label.setText("Punto B seleccionado.")
        
        # Desactivar modo de selección después de seleccionar un punto
        self.selection_mode = None
        
        # Si ya tenemos ambos puntos, podemos habilitar el botón de vista previa
        if self.pointA is not None and self.pointB is not None:
            self.preview_button.setEnabled(True)
        
        self.plotter.render()
    
    def update_preview(self):
        # Si ya tenemos una vista previa y ambos puntos, actualizarla con el nuevo diámetro
        if self.conducto_preview is not None and self.pointA is not None and self.pointB is not None:
            self.plotter.remove(self.conducto_preview)
            self.create_preview()
    
    def create_preview(self):
        # Corregir la comprobación de valores None para evitar error de NumPy
        if self.pointA is None or self.pointB is None:
            self.info_label.setText("Necesita seleccionar ambos puntos primero.")
            return
            
        # Eliminar vista previa anterior si existe
        if self.conducto_preview is not None:
            self.plotter.remove(self.conducto_preview)
        
        try:
            # Crear línea entre puntos
            line = Line(self.pointA, self.pointB)
            
            # Obtener diámetro del spinner
            radius = self.diameter_spin.value() / 2
            
            # Crear tubo alrededor de la línea con el radio especificado
            self.conducto_preview = Tube(line, r=radius, c=(0, 1, 0, 0.5), cap=False)  # Verde translúcido, sin tapas
            self.plotter.add(self.conducto_preview)
            self.plotter.render()
            
            # Habilitar botón para aplicar
            self.apply_button.setEnabled(True)
            
            self.info_label.setText("Vista previa del conducto creada. Ajuste el diámetro o presione 'Aplicar Conducto'.")
        except Exception as e:
            self.info_label.setText(f"Error al crear vista previa: {str(e)}")
            print(f"Error en create_preview: {str(e)}")
        

    def apply_conducto(self):
        if self.mesh is None or self.pointA is None or self.pointB is None:
            return
            
        try:
            # Obtener diámetro del spinner
            radius = self.diameter_spin.value() / 2
            
            # Calcular dirección del cilindro
            direction = np.array(self.pointB) - np.array(self.pointA)
            distance = np.linalg.norm(direction)
            
            if distance < 1e-6:
                self.info_label.setText("Error: Los puntos están demasiado cerca")
                return
                
            # Normalizar dirección
            direction = direction / distance
            
            # Extensión para asegurar que atraviese completamente
            modelo_size = self.mesh.diagonal_size()
            extension = modelo_size * 1.5
            
            # Puntos extendidos
            p1 = np.array(self.pointA) - direction * extension
            p2 = np.array(self.pointB) + direction * extension
            
            # Crear cilindro con Cylinder de vedo
            centro = (p1 + p2) / 2
            nueva_distancia = np.linalg.norm(p2 - p1)
            
            cylinder = Cylinder(
                pos=centro,
                r=radius, 
                height=nueva_distancia,
                axis=direction,
                cap=True,
                res=36
            )
            
            # Mostrar cilindro para depuración
            debug_cylinder = cylinder.clone().color("red", 0.3)
            self.plotter.add(debug_cylinder)
            self.plotter.render()
            
            # Realizar el corte
            result_mesh = self.mesh.clone().cut_with_mesh(cylinder)
            
            # Verificar si el resultado es válido
            if result_mesh is None or (hasattr(result_mesh, 'ncells') and result_mesh.ncells == 0):
                self.info_label.setText("Error: El corte no produjo un resultado válido")
                self.plotter.remove(debug_cylinder)
                return
                
            # Centrar el resultado en el origen
            result_mesh.normalize()
            
            # Limpiar escena
            self.plotter.remove(self.mesh)
            self.plotter.remove(debug_cylinder)
            if self.conducto_preview is not None:
                self.plotter.remove(self.conducto_preview)
                self.conducto_preview = None
            
            # Actualizar malla principal
            self.mesh = result_mesh
            
            # Restaurar propiedades visuales
            self.mesh.color((0.7, 0.7, 0.9)).alpha(self.alpha_value)
            
            # Añadir a la escena y actualizar vista
            self.plotter.add(self.mesh)
            self.plotter.reset_camera()
            self.plotter.render()
            
            self.info_label.setText("Conducto aplicado correctamente al modelo.")
            self.apply_button.setEnabled(False)
            
        except Exception as e:
            self.info_label.setText(f"Error al aplicar conducto: {str(e)}")
            print(f"Error en apply_conducto: {str(e)}")
            import traceback
            traceback.print_exc()


    def clear_selection(self):
        # Eliminar marcadores de puntos
        if self.pointA_marker is not None:
            self.plotter.remove(self.pointA_marker)
            self.pointA_marker = None
        if self.pointB_marker is not None:
            self.plotter.remove(self.pointB_marker)
            self.pointB_marker = None
            
        # Eliminar vista previa si existe
        if self.conducto_preview is not None:
            self.plotter.remove(self.conducto_preview)
            self.conducto_preview = None
            
        # Resetear puntos
        self.pointA = None
        self.pointB = None
        
        # Resetear modo de selección
        self.selection_mode = None
        
        # Deshabilitar botones
        self.preview_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        
        if self.plotter:
            self.plotter.render()
            
        self.info_label.setText("Selección de puntos reiniciada.")
    
    def reset_view(self):
        if self.plotter:
            # Resetear la cámara
            self.plotter.reset_camera()
            self.plotter.render()
    
    def add_view_box(self):
        view_box = Box(size=[0.5, 0.5, 0.5]).wireframe().alpha(0.5)
        self.plotter.add(view_box)
        self.plotter.render()
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())