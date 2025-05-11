import sys
import serial
import serial.tools.list_ports
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import time
from collections import deque

# Constants
SAMPLE_RATE = 250  # Hz
DISPLAY_TIME_SECONDS = 6
MAX_POINTS = SAMPLE_RATE * DISPLAY_TIME_SECONDS
UPDATE_INTERVAL_MS = 15  # 
FILTER_SIZE = 25  # For baseline removal
MIN_HEART_RATE = 40
MAX_HEART_RATE = 200

def find_pico_port():
    """Find the Raspberry Pi Pico's port"""
    ports = list(serial.tools.list_ports.comports())
    
    for port in ports:
        if any(id in str(port) for id in ["2E8A:000A", "2E8A:0003", "USB Serial Device"]):
            return port.device
    
    return ports[0].device if ports else None

class ECGApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECG Monitor")
        self.setGeometry(100, 100, 800, 500)
        
        # Setup variables
        self.serial = None
        self.timer = QtCore.QTimer()
        self.data_buffer = deque(maxlen=MAX_POINTS)
        self.last_update_time = time.time()
        self.data_count = 0
        self.heart_rate_history = deque(maxlen=5)
        
        self.setup_ui()
        
        # Connect signals
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.timer.timeout.connect(self.update_plot)
        
        self.refresh_ports()
        
        # Auto-connect if Pico found
        pico_port = find_pico_port()
        if pico_port:
            index = self.port_combo.findText(pico_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
                self.toggle_connection()
    
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Port controls
        port_layout = QtWidgets.QHBoxLayout()
        self.port_combo = QtWidgets.QComboBox()
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.status_label = QtWidgets.QLabel("Status: Disconnected")
        
        port_layout.addWidget(QtWidgets.QLabel("Port:"))
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)
        port_layout.addWidget(self.connect_button)
        port_layout.addWidget(self.status_label)
        
        # Plot setup
        pg.setConfigOptions(antialias=False)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Amplitude')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setRange(xRange=(0, DISPLAY_TIME_SECONDS), padding=0)
        self.plot_widget.setYRange(0, 4095)
        self.plot_curve = self.plot_widget.plot(pen=pg.mkPen('g', width=1.5))
        
        # Heart rate and signal quality indicators
        info_layout = QtWidgets.QHBoxLayout()
        self.hr_label = QtWidgets.QLabel("Heart Rate: -- BPM")
        self.hr_label.setStyleSheet("font-size: 24px; color: green;")
        self.signal_quality_label = QtWidgets.QLabel("Signal Quality: --")
        info_layout.addWidget(self.hr_label)
        info_layout.addWidget(self.signal_quality_label)
        
        # Debug area
        self.debug_text = QtWidgets.QTextEdit()
        self.debug_text.setMaximumHeight(60)
        self.debug_text.setReadOnly(True)
        
        layout.addLayout(port_layout)
        layout.addWidget(self.plot_widget)
        layout.addLayout(info_layout)
        layout.addWidget(self.debug_text)
    
    def log_debug(self, message):
        """Add debug message"""
        self.debug_text.append(f"{time.strftime('%H:%M:%S')}: {message}")
        self.debug_text.verticalScrollBar().setValue(
            self.debug_text.verticalScrollBar().maximum()
        )
    
    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            self.port_combo.addItem(port.device)
        
        pico_port = find_pico_port()
        if pico_port:
            index = self.port_combo.findText(pico_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
                self.status_label.setText(f"Pico detected at {pico_port}")
    
    def toggle_connection(self):
        """Connect or disconnect from serial port"""
        if self.serial is None or not self.serial.is_open:
            try:
                port = self.port_combo.currentText()
                self.log_debug(f"Connecting to {port}")
                
                self.serial = serial.Serial(port, 115200, timeout=0.5)
                self.serial.reset_input_buffer()
                
                self.status_label.setText(f"Connected: {port}")
                self.connect_button.setText("Disconnect")
                
                # Reset data
                self.data_buffer.clear()
                self.data_count = 0
                self.heart_rate_history.clear()
                
                self.timer.start(UPDATE_INTERVAL_MS)
                self.last_update_time = time.time()
                
            except Exception as e:
                self.log_debug(f"Connection error: {str(e)}")
                self.status_label.setText(f"Error: {str(e)}")
        else:
            self.timer.stop()
            self.serial.close()
            self.serial = None
            self.status_label.setText("Disconnected")
            self.connect_button.setText("Connect")
    
    def update_plot(self):
        """Update plot with new data"""
        if not self.serial or not self.serial.is_open:
            return
            
        bytes_waiting = self.serial.in_waiting
        if bytes_waiting <= 0:
            return
            
        try:
            raw_data = self.serial.read(bytes_waiting)
            lines = raw_data.decode('utf-8', errors='replace').strip().split('\n')
            
            new_data_count = 0
            lead_off_detected = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    value = int(line)
                    
                    if value == -1:
                        lead_off_detected = True
                    else:
                        self.data_buffer.append(value)
                        new_data_count += 1
                except ValueError:
                    continue
            
            # Update signal quality indicator
            if lead_off_detected:
                self.signal_quality_label.setText("Signal Quality: Lead Off")
                self.signal_quality_label.setStyleSheet("color: red;")
            else:
                self.signal_quality_label.setText("Signal Quality: Good")
                self.signal_quality_label.setStyleSheet("color: green;")
            
            if new_data_count > 0:
                self.data_count += new_data_count
                
                data_array = np.array(self.data_buffer)
                time_values = np.linspace(0, len(data_array) / SAMPLE_RATE, len(data_array))
                self.plot_curve.setData(time_values, data_array)
                
                # Calculate stats once per second
                now = time.time()
                elapsed = now - self.last_update_time
                
                if elapsed >= 1.0:
                    if not lead_off_detected and len(data_array) >= SAMPLE_RATE:
                        self.update_heart_rate(data_array)
                    
                    self.data_count = 0
                    self.last_update_time = now
        
        except Exception as e:
            self.log_debug(f"Error: {str(e)}")
    
    def update_heart_rate(self, data):
        """Calculate heart rate from ECG data"""
        try:
            # Filter to remove baseline
            filtered_data = data - np.convolve(data, np.ones(FILTER_SIZE)/FILTER_SIZE, mode='same')
            
            # Find peaks (R waves)
            signal_mean = np.mean(filtered_data)
            signal_std = np.std(filtered_data)
            threshold = signal_mean + 1.5 * signal_std
            
            peaks = []
            for i in range(5, len(filtered_data)-5):
                if (filtered_data[i] > threshold and 
                    filtered_data[i] > filtered_data[i-1] and 
                    filtered_data[i] > filtered_data[i+1]):
                    # Check if highest in vicinity
                    window_start = max(0, i-15)
                    window_end = min(len(filtered_data), i+15)
                    if filtered_data[i] == max(filtered_data[window_start:window_end]):
                        peaks.append(i)
            
            if len(peaks) >= 2:
                intervals = [peaks[i+1] - peaks[i] for i in range(len(peaks)-1)]
                
                avg_interval_sec = np.mean(intervals) / SAMPLE_RATE
                heart_rate = int(60 / avg_interval_sec)
                
                if MIN_HEART_RATE <= heart_rate <= MAX_HEART_RATE:
                    self.heart_rate_history.append(heart_rate)
                    avg_hr = int(sum(self.heart_rate_history) / len(self.heart_rate_history))
                    
                    self.hr_label.setText(f"Heart Rate: {avg_hr} BPM")
                    
                    if avg_hr < 60:
                        self.hr_label.setStyleSheet("font-size: 24px; color: blue;")  # Low
                    elif avg_hr > 100:
                        self.hr_label.setStyleSheet("font-size: 24px; color: red;")   # High
                    else:
                        self.hr_label.setStyleSheet("font-size: 24px; color: green;") # Normal
                    
                    return
            
            self.hr_label.setText("Heart Rate: -- BPM")
            
        except Exception as e:
            self.log_debug(f"Heart rate calculation error: {str(e)}")
    
    def closeEvent(self, event):
        """Clean up on exit"""
        if self.serial and self.serial.is_open:
            self.serial.close()
        event.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ECGApp()
    window.show()
    sys.exit(app.exec_())