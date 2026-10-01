import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import json
import threading
import time
import cv2
import os
from datetime import datetime
import numpy as np
from PIL import Image, ImageTk

class Scanner3DApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Interfaz para Escáner 3D")
        self.root.geometry("1200x800")
        
        # Variables para la conexión serial
        self.serial_port = None
        self.is_connected = False
        self.scanning = False
        self.scan_thread = None
        self.read_thread = None
        self.stop_threads = False
        
        # Variables para la cámara
        self.camera = None
        self.camera_connected = False
        self.camera_thread = None
        self.current_image = None
        
        # Variables para guardar configuraciones
        self.y_correction = tk.DoubleVar(value=1.0)
        self.z_correction = tk.DoubleVar(value=9.0)
        self.scan_folder = tk.StringVar(value=os.path.expanduser("~/scanner3d_images"))
        
        # Crear directorio para imágenes si no existe
        if not os.path.exists(self.scan_folder.get()):
            try:
                os.makedirs(self.scan_folder.get())
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear el directorio para imágenes: {str(e)}")
        
        # Crear la interfaz
        self.create_widgets()
        
        # Intentar conectar al iniciar
        self.root.after(1000, self.connect_device)
        
    def create_widgets(self):
        # Marco principal con 2 columnas
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Marco izquierdo para controles y consola
        left_frame = ttk.Frame(main_frame, padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Marco derecho para la cámara
        right_frame = ttk.Frame(main_frame, padding="5")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Panel superior izquierdo - Conexión y estado
        status_frame = ttk.LabelFrame(left_frame, text="Estado", padding="10")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botones de conexión
        self.conn_button = ttk.Button(status_frame, text="Conectar", command=self.connect_device)
        self.conn_button.pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(status_frame, text="Desconectado", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.cam_status_label = ttk.Label(status_frame, text="Cámara: Desconectada", foreground="red")
        self.cam_status_label.pack(side=tk.LEFT, padx=10)
        
        # Panel de control principal
        control_frame = ttk.LabelFrame(left_frame, text="Controles", padding="10")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botones de control en una cuadrícula de 2 columnas
        btn_start = ttk.Button(control_frame, text="Iniciar Escaneo", command=self.start_scan)
        btn_start.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        btn_pause = ttk.Button(control_frame, text="Pausar", command=self.pause_scan)
        btn_pause.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        btn_resume = ttk.Button(control_frame, text="Reanudar", command=self.resume_scan)
        btn_resume.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        btn_stop = ttk.Button(control_frame, text="Detener", command=self.stop_scan)
        btn_stop.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        btn_reset = ttk.Button(control_frame, text="Resetear", command=self.reset_system)
        btn_reset.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        btn_capture = ttk.Button(control_frame, text="Capturar Foto", command=self.manual_capture)
        btn_capture.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # Control de giro individual
        move_frame = ttk.LabelFrame(left_frame, text="Posicionamiento Manual", padding="10")
        move_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Controles para mover Y
        ttk.Label(move_frame, text="Ángulo Y (0-360):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.y_angle = ttk.Spinbox(move_frame, from_=0, to=360, increment=10, width=10)
        self.y_angle.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.y_angle.set("0")
        ttk.Button(move_frame, text="Mover Y", command=self.move_y).grid(row=0, column=2, padx=5, pady=5)
        
        # Controles para mover Z
        ttk.Label(move_frame, text="Ángulo Z (0-135):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.z_angle = ttk.Spinbox(move_frame, from_=0, to=135, increment=10, width=10)
        self.z_angle.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.z_angle.set("0")
        ttk.Button(move_frame, text="Mover Z", command=self.move_z).grid(row=1, column=2, padx=5, pady=5)
        
        # Panel de factores de corrección
        correction_frame = ttk.LabelFrame(left_frame, text="Factores de Corrección", padding="10")
        correction_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Factor Y
        ttk.Label(correction_frame, text="Factor Y:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        y_correction_entry = ttk.Spinbox(correction_frame, from_=0.1, to=20.0, increment=0.1, textvariable=self.y_correction, width=10)
        y_correction_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(correction_frame, text="Aplicar Y", command=self.set_y_correction).grid(row=0, column=2, padx=5, pady=5)
        
        # Factor Z
        ttk.Label(correction_frame, text="Factor Z:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        z_correction_entry = ttk.Spinbox(correction_frame, from_=0.1, to=20.0, increment=0.1, textvariable=self.z_correction, width=10)
        z_correction_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(correction_frame, text="Aplicar Z", command=self.set_z_correction).grid(row=1, column=2, padx=5, pady=5)
        
        # Panel para la configuración del escaneo
        scan_config_frame = ttk.LabelFrame(left_frame, text="Configuración de Escaneo", padding="10")
        scan_config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(scan_config_frame, text="Carpeta para imágenes:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(scan_config_frame, textvariable=self.scan_folder, width=30).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(scan_config_frame, text="Examinar", command=self.select_folder).grid(row=0, column=2, padx=5, pady=5)
        
        # Panel de consola para mensajes
        console_frame = ttk.LabelFrame(left_frame, text="Mensajes del Escáner", padding="10")
        console_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.console = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD, height=10)
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)
        
        # Panel para la vista de la cámara
        camera_frame = ttk.LabelFrame(right_frame, text="Vista de la Cámara", padding="10")
        camera_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.camera_canvas = tk.Canvas(camera_frame, bg="black")
        self.camera_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Barra de estado en la parte inferior
        self.statusbar = ttk.Label(self.root, text="Listo", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def select_folder(self):
        folder = filedialog.askdirectory(initialdir=self.scan_folder.get())
        if folder:
            self.scan_folder.set(folder)
            # Crear directorio si no existe
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo crear el directorio: {str(e)}")
    
    def connect_device(self):
        """Conectar al dispositivo y a la cámara"""
        self.connect_serial()
        self.connect_camera()
    
    def connect_serial(self):
        """Conectar al dispositivo por puerto serial"""
        if self.is_connected:
            # Desconectar si ya está conectado
            try:
                if self.read_thread and self.read_thread.is_alive():
                    self.stop_threads = True
                    self.read_thread.join(timeout=1.0)
                
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.close()
                    
                self.is_connected = False
                self.conn_button.config(text="Conectar")
                self.status_label.config(text="Desconectado", foreground="red")
                self.log_message("Desconectado del escáner")
            except Exception as e:
                messagebox.showerror("Error", f"Error al desconectar: {str(e)}")
            return
        
        # Intentar conectar
        try:
            # Puerto por defecto en Linux para Arduino/Seeeduino
            port = '/dev/ttyACM0'
            self.serial_port = serial.Serial(port, 115200, timeout=1)
            
            self.is_connected = True
            self.stop_threads = False
            self.conn_button.config(text="Desconectar")
            self.status_label.config(text="Conectado", foreground="green")
            self.log_message(f"Conectado al escáner en {port}")
            
            # Iniciar hilo para leer mensajes del puerto serial
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Obtener estado inicial
            self.root.after(1000, self.get_status)
            
        except Exception as e:
            self.is_connected = False
            messagebox.showerror("Error de Conexión", f"No se pudo conectar al escáner: {str(e)}\n\nAsegúrate de que el dispositivo esté conectado y que /dev/ttyACM0 existe y es accesible.")
            self.log_message(f"Error al conectar: {str(e)}")
    
    def connect_camera(self):
        """Conectar a la cámara usando OpenCV"""
        # Desconectar si ya está conectada
        if self.camera_connected:
            try:
                if self.camera is not None:
                    self.camera.release()
                self.camera_connected = False
                self.cam_status_label.config(text="Cámara: Desconectada", foreground="red")
                self.log_message("Cámara desconectada")
            except Exception as e:
                messagebox.showerror("Error", f"Error al desconectar la cámara: {str(e)}")
            return
        
        # Intentar conectar
        try:
            # Indice de la cámara para /dev/video2 sería 2 en Linux
            camera_index = 2  # Ajusta según sea necesario
            self.camera = cv2.VideoCapture(camera_index)
            
            if not self.camera.isOpened():
                raise Exception("No se pudo abrir la cámara")
                
            self.camera_connected = True
            self.cam_status_label.config(text="Cámara: Conectada", foreground="green")
            self.log_message(f"Cámara conectada en índice {camera_index}")
            
            # Iniciar hilo para actualizar la vista de la cámara
            self.camera_thread = threading.Thread(target=self.update_camera_feed)
            self.camera_thread.daemon = True
            self.camera_thread.start()
            
        except Exception as e:
            self.camera_connected = False
            messagebox.showerror("Error de Cámara", f"No se pudo conectar a la cámara: {str(e)}\n\nAsegúrate de que la cámara esté conectada y que /dev/video2 existe y es accesible.")
            self.log_message(f"Error al conectar la cámara: {str(e)}")
    
    def update_camera_feed(self):
        """Actualizar la vista de la cámara"""
        while self.camera_connected and not self.stop_threads:
            try:
                ret, frame = self.camera.read()
                if ret:
                    self.current_image = frame.copy()
                    # Convertir el frame a formato para Tkinter
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_pil = Image.fromarray(frame_rgb)
                    
                    # Redimensionar para ajustar al canvas
                    canvas_width = self.camera_canvas.winfo_width()
                    canvas_height = self.camera_canvas.winfo_height()
                    
                    if canvas_width > 1 and canvas_height > 1:
                        # Calcular proporción para mantener aspecto
                        img_width, img_height = frame_pil.size
                        ratio = min(canvas_width/img_width, canvas_height/img_height)
                        new_size = (int(img_width*ratio), int(img_height*ratio))
                        frame_pil = frame_pil.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convertir a PhotoImage
                    self.photo = ImageTk.PhotoImage(image=frame_pil)
                    
                    # Actualizar canvas (desde el hilo principal)
                    self.root.after(1, lambda: self.update_canvas())
            except Exception as e:
                self.log_message(f"Error en cámara: {str(e)}")
                self.camera_connected = False
                break
                
            time.sleep(0.03)  # ~30 FPS
    
    def update_canvas(self):
        """Actualizar el canvas con la imagen actual (llamado desde el hilo principal)"""
        try:
            # Obtener dimensiones
            canvas_width = self.camera_canvas.winfo_width()
            canvas_height = self.camera_canvas.winfo_height()
            
            if hasattr(self, 'photo'):
                # Limpiar y dibujar nueva imagen
                self.camera_canvas.delete("all")
                # Centrar imagen
                x = (canvas_width - self.photo.width()) // 2
                y = (canvas_height - self.photo.height()) // 2
                self.camera_canvas.create_image(x, y, anchor=tk.NW, image=self.photo)
        except Exception as e:
            self.log_message(f"Error al actualizar vista: {str(e)}")
    
    def read_serial(self):
        """Leer mensajes del puerto serial en un hilo separado"""
        while not self.stop_threads and self.is_connected:
            try:
                if self.serial_port and self.serial_port.is_open:
                    # Leer línea del puerto serial
                    line = self.serial_port.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        # Procesar línea (desde el hilo principal)
                        self.root.after(1, lambda l=line: self.process_serial_message(l))
            except Exception as e:
                self.root.after(1, lambda e=e: self.handle_serial_error(e))
                break
                
            time.sleep(0.01)
    
    def handle_serial_error(self, error):
        """Manejar errores de comunicación serial"""
        self.log_message(f"Error de comunicación: {str(error)}")
        self.is_connected = False
        self.status_label.config(text="Error de conexión", foreground="red")
        self.conn_button.config(text="Conectar")
        messagebox.showerror("Error", f"Se perdió la conexión con el escáner: {str(error)}")
    
    def process_serial_message(self, message):
        """Procesar mensajes recibidos del puerto serial"""
        # Registrar mensaje en consola
        self.log_message(f"← {message}")
        
        # Procesar mensaje según su formato
        if message.startswith("OK:"):
            try:
                # Extraer JSON de la respuesta
                json_str = message[3:]
                response = json.loads(json_str)
                self.statusbar.config(text=f"Último comando ejecutado correctamente")
            except json.JSONDecodeError:
                self.log_message("Error al procesar respuesta JSON")
                
        elif message.startswith("ERROR:"):
            try:
                # Extraer JSON del error
                json_str = message[6:]
                error_info = json.loads(json_str)
                error_message = error_info.get("message", "Error desconocido")
                self.statusbar.config(text=f"Error: {error_message}")
                # Para errores importantes, mostrar un popup
                messagebox.showwarning("Error del Escáner", error_message)
            except json.JSONDecodeError:
                self.log_message("Error al procesar mensaje de error JSON")
                
        elif message.startswith("STATUS:"):
            try:
                # Extraer JSON del estado
                json_str = message[7:]
                status = json.loads(json_str)
                
                # Actualizar información de estado en la interfaz
                state_names = ["IDLE", "SCANNING", "PAUSED", "CALIBRATING"]
                state_text = state_names[status.get("state", 0)]
                
                status_text = f"Estado: {state_text} | "
                status_text += f"Ángulo Y: {status.get('y_angle', 0):.1f}° | "
                status_text += f"Ángulo Z: {status.get('z_angle', 0):.1f}° | "
                status_text += f"Progreso: {status.get('z_step', 0)}/{status.get('total_z_steps', 0)}"
                
                self.statusbar.config(text=status_text)
            except json.JSONDecodeError:
                self.log_message("Error al procesar información de estado JSON")
        
        # Si se detecta la señal de fotografiar durante el escaneo
        elif "fotografiar" in message.lower() and self.scanning:
            self.capture_image()
    
    def send_command(self, command):
        """Enviar un comando al dispositivo"""
        if not self.is_connected:
            messagebox.showwarning("Advertencia", "El escáner no está conectado")
            return False
        
        try:
            # Registrar comando en la consola
            self.log_message(f"→ {command}")
            
            # Enviar comando al puerto serial
            self.serial_port.write(f"{command}\n".encode())
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al enviar comando: {str(e)}")
            self.log_message(f"Error al enviar comando: {str(e)}")
            return False
    
    def get_status(self):
        """Obtener el estado actual del escáner"""
        if self.is_connected:
            self.send_command("PY:GET_STATUS")
    
    def start_scan(self):
        """Iniciar el proceso de escaneo"""
        if not self.is_connected:
            messagebox.showwarning("Advertencia", "Conecta el escáner primero")
            return
            
        if not self.camera_connected:
            response = messagebox.askyesno("Advertencia", "La cámara no está conectada. ¿Deseas continuar sin ella?")
            if not response:
                return
        
        # Crear carpeta para este escaneo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_scan_folder = os.path.join(self.scan_folder.get(), f"scan_{timestamp}")
        
        try:
            if not os.path.exists(self.current_scan_folder):
                os.makedirs(self.current_scan_folder)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear la carpeta para el escaneo: {str(e)}")
            return
        
        # Iniciar escaneo
        success = self.send_command("PY:START_SCAN")
        if success:
            self.scanning = True
            self.log_message(f"Iniciando escaneo en carpeta: {self.current_scan_folder}")
            
            # Actualizar estado periódicamente durante el escaneo
            self.scan_thread = threading.Thread(target=self.monitor_scan)
            self.scan_thread.daemon = True
            self.scan_thread.start()
    
    def monitor_scan(self):
        """Monitorear el progreso del escaneo"""
        while self.scanning and not self.stop_threads:
            # Actualizar estado cada 2 segundos
            self.root.after(1, self.get_status)
            time.sleep(2)
    
    def pause_scan(self):
        """Pausar el proceso de escaneo"""
        if self.is_connected and self.scanning:
            self.send_command("PY:PAUSE_SCAN")
    
    def resume_scan(self):
        """Reanudar el proceso de escaneo"""
        if self.is_connected:
            self.send_command("PY:RESUME_SCAN")
    
    def stop_scan(self):
        """Detener el proceso de escaneo"""
        if self.is_connected and self.scanning:
            self.send_command("PY:STOP_SCAN")
            self.scanning = False
            self.log_message("Escaneo detenido")
    
    def reset_system(self):
        """Resetear el sistema a la posición inicial"""
        if self.is_connected:
            self.send_command("PY:RESET")
    
    def move_y(self):
        """Mover el motor Y a un ángulo específico"""
        if self.is_connected:
            try:
                angle = float(self.y_angle.get())
                if 0 <= angle <= 360:
                    self.send_command(f"PY:MOVE_Y:{angle}")
                else:
                    messagebox.showwarning("Advertencia", "El ángulo Y debe estar entre 0 y 360 grados")
            except ValueError:
                messagebox.showwarning("Advertencia", "Por favor ingresa un valor numérico válido")
    
    def move_z(self):
        """Mover el motor Z a un ángulo específico"""
        if self.is_connected:
            try:
                angle = float(self.z_angle.get())
                if 0 <= angle <= 135:
                    self.send_command(f"PY:MOVE_Z:{angle}")
                else:
                    messagebox.showwarning("Advertencia", "El ángulo Z debe estar entre 0 y 135 grados")
            except ValueError:
                messagebox.showwarning("Advertencia", "Por favor ingresa un valor numérico válido")
    
    def set_y_correction(self):
        """Establecer el factor de corrección para el motor Y"""
        if self.is_connected:
            try:
                factor = float(self.y_correction.get())
                if factor > 0:
                    self.send_command(f"PY:SET_Y_CORRECTION:{factor}")
                else:
                    messagebox.showwarning("Advertencia", "El factor debe ser mayor que 0")
            except ValueError:
                messagebox.showwarning("Advertencia", "Por favor ingresa un valor numérico válido")
    
    def set_z_correction(self):
        """Establecer el factor de corrección para el motor Z"""
        if self.is_connected:
            try:
                factor = float(self.z_correction.get())
                if factor > 0:
                    self.send_command(f"PY:SET_Z_CORRECTION:{factor}")
                else:
                    messagebox.showwarning("Advertencia", "El factor debe ser mayor que 0")
            except ValueError:
                messagebox.showwarning("Advertencia", "Por favor ingresa un valor numérico válido")
    
    def capture_image(self):
        """Capturar una imagen desde la cámara durante el escaneo"""
        if not self.camera_connected or self.current_image is None:
            self.log_message("No se pudo capturar imagen: cámara no disponible")
            return
        
        try:
            # Obtener la posición actual para nombrar el archivo
            timestamp = datetime.now().strftime("%H%M%S")
            filename = os.path.join(self.current_scan_folder, f"img_y{self.y_angle.get()}_z{self.z_angle.get()}_{timestamp}.jpg")
            
            # Guardar imagen
            cv2.imwrite(filename, self.current_image)
            self.log_message(f"Imagen guardada: {os.path.basename(filename)}")
        except Exception as e:
            self.log_message(f"Error al guardar imagen: {str(e)}")
    
    def manual_capture(self):
        """Capturar una imagen manualmente"""
        if not self.camera_connected:
            messagebox.showwarning("Advertencia", "La cámara no está conectada")
            return
            
        # Crear carpeta si no existe
        if not hasattr(self, 'current_scan_folder'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_scan_folder = os.path.join(self.scan_folder.get(), f"manual_{timestamp}")
            
            try:
                if not os.path.exists(self.current_scan_folder):
                    os.makedirs(self.current_scan_folder)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear la carpeta: {str(e)}")
                return
        
        # Capturar imagen
        self.capture_image()
    
    def log_message(self, message):
        """Añadir un mensaje a la consola"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Habilitar la consola para escritura
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, log_entry)
        self.console.see(tk.END)  # Desplazar hasta el final
        self.console.config(state=tk.DISABLED)
    
    def on_closing(self):
        """Función llamada al cerrar la aplicación"""
        # Detener hilos
        self.stop_threads = True
        
        # Cerrar conexiones
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
        if self.camera_connected and self.camera is not None:
            self.camera.release()
            
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = Scanner3DApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
