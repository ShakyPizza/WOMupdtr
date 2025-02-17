import sys
import threading
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit,
                             QFileDialog, QTableWidget, QTableWidgetItem, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess

class BotCommandThread(QThread):
    output_signal = pyqtSignal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            result = subprocess.run(self.command, shell=True, text=True, capture_output=True)
            output = result.stdout if result.stdout else result.stderr
            self.output_signal.emit(output)
        except Exception as e:
            self.output_signal.emit(str(e))

class BotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Bot Control Panel")
        self.setGeometry(100, 100, 600, 400)
        
        self.layout = QVBoxLayout()
        
        self.commandButton = QPushButton("Send Command")
        self.commandButton.clicked.connect(self.send_command)
        self.layout.addWidget(self.commandButton)
        
        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.layout.addWidget(self.logText)
        
        self.csvButton = QPushButton("Open CSV File")
        self.csvButton.clicked.connect(self.load_csv)
        self.layout.addWidget(self.csvButton)
        
        self.tableWidget = QTableWidget()
        self.layout.addWidget(self.tableWidget)
        
        self.setLayout(self.layout)
    
    def send_command(self):
        command = "echo Bot Command Executed"  # Replace with actual bot command
        self.logText.append(f"Executing: {command}")
        
        self.commandThread = BotCommandThread(command)
        self.commandThread.output_signal.connect(self.display_output)
        self.commandThread.start()
    
    def display_output(self, output):
        self.logText.append(output)
    
    def load_csv(self):
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)", options=options)
        
        if filePath:
            try:
                df = pd.read_csv(filePath)
                self.populate_table(df)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load CSV: {str(e)}")
    
    def populate_table(self, df):
        self.tableWidget.setRowCount(df.shape[0])
        self.tableWidget.setColumnCount(df.shape[1])
        self.tableWidget.setHorizontalHeaderLabels(df.columns)
        
        for row in range(df.shape[0]):
            for col in range(df.shape[1]):
                self.tableWidget.setItem(row, col, QTableWidgetItem(str(df.iat[row, col])))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotGUI()
    window.show()
    sys.exit(app.exec())
