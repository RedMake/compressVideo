import time
import tkinter as tk

from tkinter import filedialog, ttk
from TkinterDnD2 import DND_FILES, TkinterDnD

import threading
import queue
import os
import ffmpeg

class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window is not None:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip_window, text=self.widget['text'], background="lightyellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

upload_queue = queue.Queue(maxsize=10)  
cancel_compression_flag = False
ffmpeg_process = None
compression_tasks = []  

def resize_video(video_absolute_path: str, output_file_absolute_path: str, size_upper_bound: int, two_pass: bool=True, quality_mode: str='medium') -> str:
    global ffmpeg_process  
    try:
        probe_json_representation = ffmpeg.probe(video_absolute_path)
    except ffmpeg.Error as e:
        error_message = e.stderr.decode("utf-8") 
        error_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffprobe_error_log.txt")
        
        with open(error_path, "w", encoding="utf-8") as file:
            file.write(error_message)
            file.close()
        raise Exception(f"Error de ffprobe: \n \n      Archivo de error creado en: \n\n{error_path} ")
    
    duration = float(probe_json_representation['format']['duration'])
    streams = probe_json_representation['streams']
    stream = next((stream for stream in streams if stream['codec_type'] == 'audio'), None)

    if stream is None:
        raise Exception("El archivo no contiene audio.")

    bit_rate = stream['bit_rate']
    audio_bitrate = float(bit_rate)
    target_total_bitrate = (size_upper_bound * 1024 * 8) / (1.073741824 * duration)
    min_audio_bitrate = 32000
    video_bitrate = target_total_bitrate - audio_bitrate
    max_audio_bitrate = 256000

    if quality_mode == 'maxQuality':
        video_bitrate = video_bitrate * 6  
    if quality_mode == 'super':
        video_bitrate = video_bitrate * 4  
    if quality_mode == 'ultra-high':
        video_bitrate = video_bitrate * 2.5  
    if quality_mode == 'high':
        video_bitrate = video_bitrate * 1.5  
    elif quality_mode == 'low':
        video_bitrate = video_bitrate * 0.75 

    if 10 * audio_bitrate > target_total_bitrate:
        audio_bitrate = target_total_bitrate / 10
        if audio_bitrate < min_audio_bitrate < target_total_bitrate:
            audio_bitrate = min_audio_bitrate
        elif audio_bitrate > max_audio_bitrate:
            audio_bitrate = max_audio_bitrate

    i = ffmpeg.input(video_absolute_path)
    if two_pass:
        ffmpeg.output(
            i,
            '/dev/null' if os.path.exists('/dev/null') else 'NUL',
            **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 1, 'f': 'mp4'}
        ).overwrite_output().run()

    ffmpeg_process = (
        ffmpeg.output(
            i,
            output_file_absolute_path,
            **{'c:v': 'libx264', 'b:v': video_bitrate, 'c:a': 'aac', 'b:a': audio_bitrate}
        )
        .overwrite_output()
        .run_async(pipe_stderr=True)
    )
    
    while True:
        if cancel_compression_flag:
            ffmpeg_process.terminate()  
            raise Exception('Compresión cancelada.')

        retcode = ffmpeg_process.poll()
        output = ffmpeg_process.stderr.readline()
        cancel_button.pack_forget()
        log_progress(output.decode('utf-8').strip())
        if retcode is not None: 
            break
        
        time.sleep(0.1)

    if os.path.getsize(output_file_absolute_path) <= size_upper_bound * 1024:
        return output_file_absolute_path
    else:
        raise Exception('Error en la compresión')

def select_video_file():
    file_path = filedialog.askopenfilename(
        title="Selecciona un archivo de video",
        filetypes=[("Archivos de video", "*.mp4 *.mov *.avi *.mkv *.flv *.wmv")],
    )
    valid_extensions = (".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv")
    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() in valid_extensions:
        return file_path
    else:
        return "False"

def select_output_file():
    output_path = filedialog.asksaveasfilename(
        title="Guardar video comprimido como",
        defaultextension=".mp4",
        filetypes=[("Archivo MP4", "*.mp4")],
    )
    return output_path

def start_compression_from_queue():
    global cancel_compression_flag 
    flag_error = False
    while not upload_queue.empty():
        video_info = upload_queue.get()
        video_path = video_info['video_path']
        output_path = video_info['output_path']
        size_upper_bound = video_info['size_upper_bound']
        quality_mode = video_info['quality_mode']

        try:
            progress_var.set(f"Comprimiendo {os.path.basename(video_path)}...")
            file_absolute_path = resize_video(
                video_absolute_path=video_path,
                size_upper_bound=size_upper_bound,
                output_file_absolute_path=output_path,
                quality_mode=quality_mode,
            )
            progress_var.set(f"Comprimido")
            log_progress(f"Video guardado en: {file_absolute_path}")
        except Exception as e:
            progress_var.set(f"Terminado")
            if "Error" in str(e) or "error" in str(e):
                flag_error = True
                pack_set(3)
            log_progress(f"Aviso: {e}")
            
            
        if cancel_compression_flag:
            break
    
    if flag_error != True:
        pack_set(1)

def queue_compression(video_path, output_path, size_upper_bound, quality_mode):
    if upload_queue.qsize() < upload_queue.maxsize:
        upload_queue.put({
            'video_path': video_path,
            'output_path': output_path,
            'size_upper_bound': size_upper_bound,
            'quality_mode': quality_mode
        })
        if upload_queue.qsize() == 1:  
            threading.Thread(target=start_compression_from_queue).start()
    else:
        progress_var.set("El límite de la cola ha sido alcanzado (10 archivos).")

def on_start_compression():
    global cancel_compression_flag  
    video_path = select_video_file()
    if video_path:
        output_path = select_output_file()
        if output_path:
            quality_mode = get_quality_mode()
            progress_var.set("Añadiendo a la cola...")
            
            pack_set(0)
            cancel_compression_flag = False 
            
            queue_compression(video_path, output_path, 50 * 1000, quality_mode)
        else:
            progress_var.set("No se seleccionó un destino.")
    elif video_path == "False":
        progress_var.set("No se seleccionó ningún archivo de video valido.")
    else:
        progress_var.set("No se seleccionó ningún archivo de video.")

def cancel_compression():
    global cancel_compression_flag
    cancel_compression_flag = True 
    progress_var.set("Cancelando compresión, esto puede llevar unos minutos...")
    pack_set(2)

def pack_set(flag: int):
    match flag:
        case 0:
            root.geometry("480x200")
            progress_text_area.pack_forget()
            quality_label.pack_forget()
            quality_maxQuality.pack_forget()
            quality_super.pack_forget()
            quality_ultra_high.pack_forget()
            quality_high.pack_forget()
            quality_medium.pack_forget()
            quality_low.pack_forget()
            # list_label.pack_forget()
            # listdb.pack_forget()
            start_button.pack_forget()
            cancel_button.pack()
        case 1:
            root.geometry("480x510")
            progress_text_area.pack(fill=tk.BOTH, padx=10, pady=5 )
            quality_label.pack()
            quality_maxQuality.pack()
            quality_super.pack()
            quality_ultra_high.pack()
            quality_high.pack()
            quality_medium.pack()
            quality_low.pack()
            # list_label.pack(pady=10)
            # listdb.pack(fill=tk.BOTH , padx=10, pady=5)
            start_button.pack(pady=10)
        case 2:
            root.geometry("480x100")
            cancel_button.pack_forget()
        case 3:
            root.geometry("480x200")
            quality_label.pack_forget()
            quality_maxQuality.pack_forget()
            quality_super.pack_forget()
            quality_ultra_high.pack_forget()
            quality_high.pack_forget()
            quality_medium.pack_forget()
            quality_low.pack_forget()
            # list_label.pack_forget()
            # listdb.pack_forget()
            start_button.pack_forget()

def update_tooltip():
    tooltip.text = progress_var.get()
    full_text = progress_var.get()
    truncated_text = (full_text[:40] + '...') if len(full_text) > 40 else full_text
    progress_label.config(text=truncated_text)

def log_progress(message):
    progress_text_area.pack()
    progress_text_area.config(state="normal")
    progress_text_area.insert(tk.END, f"{message}\n")
    progress_text_area.yview(tk.END)
    progress_text_area.config(state="disabled")

def on_closing():
    cancel_compression()  
    root.destroy()

def get_quality_mode():
    quality_mode = 'maxQuality' if quality_var.get() == 4 else \
                   'super' if quality_var.get() == 3 else \
                   'ultra-high' if quality_var.get() == 2 else \
                   'high' if quality_var.get() == 1 else \
                   'medium' if quality_var.get() == 0 else \
                   'low' if quality_var.get() == -1 else 'low'
    return quality_mode
                   
def on_drop(event):
    
    
    data = event.data

    splitters = ['} {', ' {', '}', '} ', ' ']

    paths = [data]

    for splitter in splitters:
        new_paths = []
        for part in paths:
            new_paths.extend(part.split(splitter))
        paths = new_paths

    cleaned_paths = [path.strip('{} ') for path in paths]

    valid_extensions = (".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv")
    video_paths = [path for path in cleaned_paths if path.endswith(valid_extensions)]
    flag_continue = True  

    for path in video_paths:
        _, file_extension = os.path.splitext(path)  
        if file_extension.lower() not in valid_extensions:
            flag_continue = False
            break  

    if not flag_continue:
        progress_var.set("Los archivos seleccionados no son válidos.")
        return

    if len(video_paths) > 10:
        progress_var.set("El límite de la cola ha sido alcanzado (10 archivos).")
        return
    
    output_path = select_output_file() 

    if output_path:
        quality_mode = get_quality_mode()
        
        for video_path in video_paths:
            if video_path: 
                queue_compression(video_path, output_path, 50 * 1000, quality_mode)

        video_paths.clear() 

    else:
        progress_var.set("No se seleccionó un destino.")


if __name__ == '__main__':
    root = TkinterDnD.Tk()  
    root.title("Compresor de Video")
    root.geometry("480x410")
    root.resizable(False, True)

    progress_var = tk.StringVar()
    progress_label = ttk.Label(root, textvariable=progress_var, wraplength=460)
    progress_label.pack(pady=10)

    progress_text_area = tk.Text(root, height=8, wrap='word')
    progress_text_area.pack(fill=tk.BOTH, padx=10, pady=5 )
    progress_text_area.pack_forget()
    
    quality_var = tk.IntVar(value=0)
    quality_label = ttk.Label(root, text="Seleccionar calidad:")
    quality_label.pack()

    quality_maxQuality = ttk.Radiobutton(root, text="Maxima Calidad", variable=quality_var, value=4)
    quality_maxQuality.pack(anchor="center")

    quality_super = ttk.Radiobutton(root, text="Super", variable=quality_var, value=3)
    quality_super.pack(anchor="center")

    quality_ultra_high = ttk.Radiobutton(root, text="Muy Alta", variable=quality_var, value=2)
    quality_ultra_high.pack(anchor="center")

    quality_high = ttk.Radiobutton(root, text="Alta", variable=quality_var, value=1)
    quality_high.pack(anchor="center")

    quality_medium = ttk.Radiobutton(root, text="Media", variable=quality_var, value=0)
    quality_medium.pack(anchor="center")

    quality_low = ttk.Radiobutton(root, text="Baja", variable=quality_var, value=-1)
    quality_low.pack(anchor="center")

    # list_label = ttk.Label(root, text="Arrastre los videos aquí o seleccione de manera unica en el boton", wraplength=460)
    # list_label.pack(pady=10)
    
    # listdb = tk.Listbox(root, selectmode=tk.SINGLE, background= "#ffe0d6", height=8)
    # listdb.drop_target_register(DND_FILES)
    # listdb.dnd_bind('<<Drop>>', on_drop)
    # listdb.pack(fill=tk.BOTH , padx=10, pady=5)
   

    start_button = ttk.Button(root, text="Comenzar compresión", command=on_start_compression)
    start_button.pack(pady=10)

    cancel_button = ttk.Button(root, text="Cancelar compresión", command=cancel_compression)
    cancel_button.pack(pady=10)
    cancel_button.pack_forget()

    tooltip = Tooltip(progress_label)
    progress_var.trace_add("write", lambda *args: update_tooltip())
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
