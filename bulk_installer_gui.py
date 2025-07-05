#!/usr/bin/env python3
"""
Bulk Software Installer GUI
A user-friendly graphical interface for the bulk installer
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import threading
import queue
import os
import sys
from pathlib import Path
from bulk_installer import BulkInstaller, OperationMode, Platform

class BulkInstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bulk Software Installer")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Variables
        self.config_file = tk.StringVar(value="apps.json")
        self.selected_mode = tk.StringVar(value="install")
        self.workers = tk.IntVar(value=1)
        self.selected_tags = []
        self.log_queue = queue.Queue()
        self.installer = None
        
        # Setup UI
        self.setup_ui()
        self.setup_logging()
        
        # Start log consumer
        self.consume_logs()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Bulk Software Installer", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # Config file selection
        ttk.Label(config_frame, text="Config File:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        config_entry = ttk.Entry(config_frame, textvariable=self.config_file, width=50)
        config_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(config_frame, text="Browse", command=self.browse_config).grid(row=0, column=2)
        
        # Load config button
        ttk.Button(config_frame, text="Load Configuration", 
                  command=self.load_configuration).grid(row=1, column=0, columnspan=3, pady=(10, 0))
        
        # Operation section
        operation_frame = ttk.LabelFrame(main_frame, text="Operation", padding="10")
        operation_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Mode selection
        ttk.Label(operation_frame, text="Mode:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        mode_combo = ttk.Combobox(operation_frame, textvariable=self.selected_mode, 
                                 values=[m.value for m in OperationMode], state="readonly")
        mode_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Workers
        ttk.Label(operation_frame, text="Workers:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        workers_spin = ttk.Spinbox(operation_frame, from_=1, to=10, textvariable=self.workers, width=10)
        workers_spin.grid(row=0, column=3, sticky=tk.W)
        
        # Tags section
        tags_frame = ttk.LabelFrame(main_frame, text="Filter by Tags", padding="10")
        tags_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        tags_frame.columnconfigure(0, weight=1)
        
        # Available tags
        self.tags_listbox = tk.Listbox(tags_frame, selectmode=tk.MULTIPLE, height=4)
        self.tags_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Tags scrollbar
        tags_scrollbar = ttk.Scrollbar(tags_frame, orient=tk.VERTICAL, command=self.tags_listbox.yview)
        tags_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tags_listbox.configure(yscrollcommand=tags_scrollbar.set)
        
        # Tags buttons
        tags_buttons_frame = ttk.Frame(tags_frame)
        tags_buttons_frame.grid(row=0, column=2, sticky=tk.N)
        
        ttk.Button(tags_buttons_frame, text="Select All", 
                  command=self.select_all_tags).grid(row=0, column=0, pady=(0, 5))
        ttk.Button(tags_buttons_frame, text="Clear All", 
                  command=self.clear_all_tags).grid(row=1, column=0)
        
        # Log section
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="10")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=(10, 0))
        
        self.start_button = ttk.Button(button_frame, text="Start Operation", 
                                      command=self.start_operation, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                     command=self.stop_operation, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(button_frame, text="Exit", command=self.root.quit).grid(row=0, column=3)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def setup_logging(self):
        """Setup logging to GUI."""
        import logging
        
        class QueueHandler(logging.Handler):
            def __init__(self, queue):
                super().__init__()
                self.queue = queue
            
            def emit(self, record):
                self.queue.put(record)
        
        # Setup logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Add queue handler
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        queue_handler.setFormatter(formatter)
        logger.addHandler(queue_handler)
    
    def consume_logs(self):
        """Consume logs from queue and display in GUI."""
        try:
            while True:
                record = self.log_queue.get_nowait()
                msg = self.log_text.get("1.0", tk.END) + record.getMessage() + '\n'
                self.log_text.delete("1.0", tk.END)
                self.log_text.insert("1.0", msg)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.consume_logs)
    
    def browse_config(self):
        """Browse for configuration file."""
        filename = filedialog.askopenfilename(
            title="Select Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.config_file.set(filename)
    
    def load_configuration(self):
        """Load and display configuration."""
        try:
            config_path = Path(self.config_file.get())
            if not config_path.exists():
                messagebox.showerror("Error", f"Configuration file not found: {config_path}")
                return
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Extract unique tags
            tags = set()
            for app in config:
                if 'tags' in app:
                    tags.update(app['tags'])
            
            # Update tags listbox
            self.tags_listbox.delete(0, tk.END)
            for tag in sorted(tags):
                self.tags_listbox.insert(tk.END, tag)
            
            self.status_var.set(f"Loaded {len(config)} applications with {len(tags)} tags")
            messagebox.showinfo("Success", f"Configuration loaded successfully!\n{len(config)} applications found.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
    
    def select_all_tags(self):
        """Select all tags."""
        self.tags_listbox.selection_set(0, tk.END)
    
    def clear_all_tags(self):
        """Clear all tag selections."""
        self.tags_listbox.selection_clear(0, tk.END)
    
    def get_selected_tags(self):
        """Get selected tags."""
        return [self.tags_listbox.get(i) for i in self.tags_listbox.curselection()]
    
    def start_operation(self):
        """Start the bulk installation operation."""
        try:
            # Get selected tags
            selected_tags = self.get_selected_tags()
            
            # Create installer
            self.installer = BulkInstaller(self.config_file.get())
            
            # Get mode
            mode = OperationMode(self.selected_mode.get())
            
            # Start operation in separate thread
            self.operation_thread = threading.Thread(
                target=self.run_operation,
                args=(mode, self.workers.get(), selected_tags)
            )
            self.operation_thread.daemon = True
            self.operation_thread.start()
            
            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.progress.start()
            self.status_var.set("Operation in progress...")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start operation: {str(e)}")
    
    def run_operation(self, mode, workers, tags):
        """Run the operation in a separate thread."""
        try:
            results = self.installer.run(mode, workers, tags)
            
            # Update UI in main thread
            self.root.after(0, self.operation_completed, results)
            
        except Exception as e:
            self.root.after(0, self.operation_failed, str(e))
    
    def operation_completed(self, results):
        """Handle operation completion."""
        self.progress.stop()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Show results
        message = f"Operation completed!\n\n"
        message += f"Total processed: {results['total']}\n"
        message += f"Successfully processed: {len(results['installed'] + results['uninstalled'] + results['updated'])}\n"
        message += f"Skipped: {len(results['skipped'])}\n"
        message += f"Failed: {len(results['failed'])}"
        
        if results['failed']:
            messagebox.showwarning("Operation Completed", message)
        else:
            messagebox.showinfo("Operation Completed", message)
        
        self.status_var.set("Operation completed")
    
    def operation_failed(self, error):
        """Handle operation failure."""
        self.progress.stop()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Operation failed")
        messagebox.showerror("Operation Failed", f"Operation failed: {error}")
    
    def stop_operation(self):
        """Stop the current operation."""
        if hasattr(self, 'installer') and self.installer:
            # Note: This is a simplified stop mechanism
            # In a real implementation, you'd need to implement proper cancellation
            self.status_var.set("Stopping operation...")
            messagebox.showinfo("Stop", "Stop functionality would be implemented here")
    
    def clear_log(self):
        """Clear the log output."""
        self.log_text.delete("1.0", tk.END)

def main():
    """Main function to run the GUI."""
    root = tk.Tk()
    
    # Set theme if available
    try:
        style = ttk.Style()
        style.theme_use('clam')
    except:
        pass
    
    app = BulkInstallerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 