# Date: 2025-07-21
# Author: Faysal Haque
# Description: A GUI application to select distal and proximal junctions in registred images
# and copy multiple Regions of Interest (ROIs) based on the selection.
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import shutil
import re

# --- Constants ---
# You can adjust the ROI parameters and names here if needed
ROI_1_CONFIG = {"name": "50-100_distal_TF", "base": "distal", "skip": 50, "copy": 50}
ROI_2_CONFIG = {"name": "450-500_distal_TF", "base": "distal", "skip": 450, "copy": 50}
ROI_3_CONFIG = {"name": "0-300_proximal_TF", "base": "proximal", "skip": 0, "count": 300}
ROI_4_CONFIG = {"name": "40-90_proximal_TF", "base": "proximal", "skip": 40,"count": 50}

# Max display size for images in the viewer
MAX_DISPLAY_WIDTH = 800
MAX_DISPLAY_HEIGHT = 600

class ROIMarkerApp:
    """
    A GUI application for selecting distal and proximal junctions in a series of tibia microCT images and copying multiple Regions of Interest (ROIs) based on the selection.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ROI Marker and Copier")
        self.root.geometry("650x300")

        # --- State Variables ---
        self.input_folder_path = tk.StringVar()
        self.output_folder_path = tk.StringVar()
        self.image_files = []
        self.distal_index = -1
        self.proximal_index = -1
        self.current_state = "SELECT_DISTAL" # Initial state for the viewer
        self.distal_slice_info = tk.StringVar(value="Distal TF Junction Slice: Not selected")
        self.proximal_slice_info = tk.StringVar(value="Proximal TF Junction Slice: Not selected")

        # --- Main Window Widgets --
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill="both", expand=True)

        # Input folder selection
        ttk.Label(self.main_frame, text="Step 1: Select the source image folder.").pack(anchor="w")
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill="x", pady=(2, 10))
        ttk.Entry(input_frame, textvariable=self.input_folder_path, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(input_frame, text="Browse...", command=self.select_input_folder).pack(side="left", padx=(5,0))

        # Output folder selection
        ttk.Label(self.main_frame, text="Step 2: Select the destination output folder.").pack(anchor="w")
        output_frame = ttk.Frame(self.main_frame)
        output_frame.pack(fill="x", pady=(2, 10))
        ttk.Entry(output_frame, textvariable=self.output_folder_path, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(output_frame, text="Browse...", command=self.select_output_folder).pack(side="left", padx=(5,0))
        
        # --- NEW: Frame for showing selected slice info ---
        info_frame = ttk.LabelFrame(self.main_frame, text="Selection Info", padding="10")
        info_frame.pack(fill="x", pady=10)
        ttk.Label(info_frame, textvariable=self.distal_slice_info).pack(anchor="w")
        ttk.Label(info_frame, textvariable=self.proximal_slice_info).pack(anchor="w")
        
        # Start button
        self.btn_start = ttk.Button(
            self.main_frame,
            text="Start Marking Process",
            command=self.start_processing,
            state="disabled"
        )
        self.btn_start.pack(pady=20, fill="x")

        # --- Viewer Window (will be created later) ---
        self.viewer_window = None
        self.image_label = None
        self.slider = None
        self.mark_button = None
        self.status_label = None
        self.photo_image = None # To prevent garbage collection

    def _check_paths(self):
        """Enable start button if both paths are set."""
        if self.input_folder_path.get() and self.output_folder_path.get():
            self.btn_start.config(state="normal")
        else:
            self.btn_start.config(state="disabled")

    def select_input_folder(self):
        """Opens a dialog to select the input folder."""
        folder_path = filedialog.askdirectory(title="Select the Image Series Folder")
        if folder_path:
            self.input_folder_path.set(folder_path)
            self._check_paths()

    def select_output_folder(self):
        """Opens a dialog to select the output folder."""
        folder_path = filedialog.askdirectory(title="Select the Base Output Directory")
        if folder_path:
            self.output_folder_path.set(folder_path)
            self._check_paths()

    def start_processing(self):
        """Validates paths and opens the image viewer."""
        input_path = self.input_folder_path.get()
        try:
            files = [f for f in os.listdir(input_path) if f.lower().endswith(('.tif', '.tiff'))]
            
            def sort_key(filename):
                match = re.search(r'(\d+)\.tif', filename, re.IGNORECASE)
                return int(match.group(1)) if match else 0
            
            files.sort(key=sort_key)

            if not files:
                messagebox.showerror("Error", "No TIFF images found in the selected folder.")
                return

            self.image_files = files
            self.open_image_viewer()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read folder: {e}")

    def open_image_viewer(self):
        """Creates and manages the Toplevel window for image navigation and selection."""
        if self.viewer_window:
            self.viewer_window.destroy()

        self.viewer_window = tk.Toplevel(self.root)
        self.viewer_window.title("Slice Selector")

        self.status_label = ttk.Label(self.viewer_window, text="", font=("Helvetica", 12, "bold"), justify="center")
        self.status_label.pack(pady=10)
        self.image_label = ttk.Label(self.viewer_window)
        self.image_label.pack(padx=10, pady=10)

        self.slider = ttk.Scale(self.viewer_window, from_=0, to=len(self.image_files) - 1, orient="horizontal", command=lambda val: self.update_image_display(int(float(val))))
        self.slider.pack(fill="x", expand=True, padx=20, pady=5)
        
        self.mark_button = ttk.Button(self.viewer_window, text="Mark Slice", command=self.mark_slice)
        self.mark_button.pack(pady=10)
        
        self.current_state = "SELECT_DISTAL"
        self.update_status_label()
        self.update_image_display(0)

    def update_image_display(self, index):
        """Loads and displays the image at the given index."""
        try:
            filepath = os.path.join(self.input_folder_path.get(), self.image_files[index])
            with Image.open(filepath) as img:
                img.thumbnail((MAX_DISPLAY_WIDTH, MAX_DISPLAY_HEIGHT), Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo_image)
            self.update_status_label(index)
        except Exception as e:
            self.image_label.config(text=f"Error loading image: {e}")

    def update_status_label(self, index=None):
        """Updates the instructional text based on the current state."""
        if index is None:
            index = int(self.slider.get())
        
        base_text = f"Slice {index + 1} / {len(self.image_files)}"
        
        if self.current_state == "SELECT_DISTAL":
            self.status_label.config(text=f"Step 3: Select the Distal TF Junction\n{base_text}")
        elif self.current_state == "SELECT_PROXIMAL":
            self.status_label.config(text=f"Step 4: Select the Proximal TF Junction\n{base_text}")

    def mark_slice(self):
        """Handles the logic for marking distal and proximal slices."""
        current_index = int(self.slider.get())

        if self.current_state == "SELECT_DISTAL":
            self.distal_index = current_index
            self.distal_slice_info.set(f"Distal TF Junction Slice: {self.distal_index + 1}") # Update main window
            messagebox.showinfo("Marked!", f"Distal TF junction marked at slice {self.distal_index + 1}.")
            self.current_state = "SELECT_PROXIMAL"
            self.update_status_label()

        elif self.current_state == "SELECT_PROXIMAL":
            self.proximal_index = current_index
            if self.proximal_index <= self.distal_index:
                messagebox.showwarning("Warning", "Proximal junction must be after the distal junction. Please select again.")
                return
            
            self.proximal_slice_info.set(f"Proximal TF Junction Slice: {self.proximal_index + 1}") # Update main window
            messagebox.showinfo("Marked!", f"Proximal TF junction marked at slice {self.proximal_index + 1}.\n\nNow processing all ROIs...")
            self.mark_button.config(state="disabled")
            self.slider.config(state="disabled")
            self.process_all_rois()

    def _copy_roi_files(self, image_folder_name, roi_config):
        """Helper function to process and copy files for a single ROI."""
        roi_name = roi_config["name"]
        start_index, end_index = 0, 0
        
        # Determine start and end indices based on ROI type
        if roi_config.get("base") == "proximal":
            # Logic for ROI 3: look back from proximal index
            count = roi_config["count"]
            skip_count = roi_config["skip"]
            end_index = self.proximal_index + 1 - skip_count
            start_index = end_index - count
        else:  # Default to "distal" logic for ROI 1 and 2
            skip_count = roi_config["skip"]
            copy_count = roi_config["copy"]
            start_index = self.distal_index + skip_count + 1
            end_index = start_index + copy_count

        # Check for out-of-bounds
        if start_index >= len(self.image_files) or end_index > len(self.image_files) or start_index < 0:
            return f"'{roi_name}': Skipped (Region is out of image bounds)."

        # *** NEW: Construct the new directory structure ***
        # Path: output_folder / ROI_name / image_folder_name
        base_output_dir = self.output_folder_path.get()
        final_output_path = os.path.join(base_output_dir, roi_name, image_folder_name)
        os.makedirs(final_output_path, exist_ok=True)
        
        files_to_copy = self.image_files[start_index:end_index]
        for filename in files_to_copy:
            source_path = os.path.join(self.input_folder_path.get(), filename)
            dest_path = os.path.join(final_output_path, filename)
            shutil.copy2(source_path, dest_path)
            
        # Update success message to be more clear
        return f"'{roi_name}': Copied {len(files_to_copy)} files to folder '{image_folder_name}'"

    def process_all_rois(self):
        """Calculates all ROIs, creates directories, and copies the files."""
        try:
            # Get the image folder name (without " registered")
            parent_folder_name = os.path.basename(self.input_folder_path.get())
            image_folder_name = re.sub(r'\sregistered$', '', parent_folder_name, flags=re.IGNORECASE)

            # Process each defined ROI by passing the image_folder_name to the helper
            results = []
            all_roi_configs = [ROI_1_CONFIG, ROI_2_CONFIG, ROI_3_CONFIG, ROI_4_CONFIG]
            for config in all_roi_configs:
                results.append(self._copy_roi_files(image_folder_name, config))
            
            # Show final report
            report_message = f"Processing Complete!\n\n" + "\n\n".join(results)
            messagebox.showinfo("Success!", report_message)

        except Exception as e:
            messagebox.showerror("Error", f"A critical error occurred during file processing: {e}")
        finally:
            if self.viewer_window:
                self.viewer_window.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    app = ROIMarkerApp(app_root)
    app_root.mainloop()