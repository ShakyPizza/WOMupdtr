import sys
import threading
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit,
                             QFileDialog, QTableWidget, QTableWidgetItem, QMessageBox, QLineEdit)
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess


def run_bot_command(command):
    # Placeholder for the actual bot logic
    # You can replace this with direct function calls or any API logic you have
    # For now, let's just return a dummy message
    return f"Executed bot logic with command: {command}"


class BotCommandThread(QThread):
    output_signal = pyqtSignal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            output = run_bot_command(self.command)
            self.output_signal.emit(output)
        except Exception as e:
            self.output_signal.emit(str(e))


class BotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.current_df = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Bot Control Panel")
        self.setGeometry(100, 100, 600, 400)
        
        self.layout = QVBoxLayout()

        # Set Style
        self.setStyleSheet("""
        QWidget {
            font-size: 14px;
        }
        QPushButton {
            background-color: #007acc;
            color: white;
            border-radius: 4px;
            padding: 6px;
        }
        QPushButton:hover {
            background-color: #005999;
        }
        """)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # Command input
        self.commandInput = QLineEdit()
        self.commandInput.setPlaceholderText("Enter bot command here...")
        self.layout.addWidget(self.commandInput)

        # Command button
        self.commandButton = QPushButton("Send Command")
        self.commandButton.clicked.connect(self.send_command)
        self.layout.addWidget(self.commandButton)
        
        # Log text
        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.layout.addWidget(self.logText)
        
        # Save log button
        self.saveLogButton = QPushButton("Save Log")
        self.saveLogButton.clicked.connect(self.save_log)
        self.layout.addWidget(self.saveLogButton)

        # CSV Button
        self.csvButton = QPushButton("Open CSV File")
        self.csvButton.clicked.connect(self.load_csv)
        self.layout.addWidget(self.csvButton)

        # Table Search
        self.tableSearch = QLineEdit()
        self.tableSearch.setPlaceholderText("Search in table...")
        self.tableSearch.textChanged.connect(self.filter_table)
        self.layout.addWidget(self.tableSearch)

        # Table Widget
        self.tableWidget = QTableWidget()
        self.layout.addWidget(self.tableWidget)
        
        self.setLayout(self.layout)
    
    def send_command(self):
        command = self.commandInput.text().strip()
        if not command:
            QMessageBox.warning(self, "Warning", "Please enter a command.")
            return
        
        self.logText.append(f"Executing: {command}")
        
        self.commandThread = BotCommandThread(command)
        self.commandThread.output_signal.connect(self.display_output)
        self.commandThread.start()
    
    def display_output(self, output):
        self.logText.append(output)
    
    def save_log(self):
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log As",
            "",
            "Text Files (*.txt);;All Files (*)",
            options=options
        )
        if filePath:
            try:
                with open(filePath, "w", encoding="utf-8") as f:
                    f.write(self.logText.toPlainText())
                QMessageBox.information(self, "Success", "Log saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log: {str(e)}")

    def load_csv(self):
        options = QFileDialog.options()
        filePath, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)", options=options)
        
        if filePath:
            try:
                df = pd.read_csv(filePath)
                self.current_df = df
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

    def filter_table(self):
        if self.current_df is None:
            return
        
        search_text = self.tableSearch.text().lower()
        for row in range(self.current_df.shape[0]):
            row_match = False
            for col in range(self.current_df.shape[1]):
                cell_value = str(self.current_df.iat[row, col]).lower()
                if search_text in cell_value:
                    row_match = True
                    break
            self.tableWidget.setRowHidden(row, not row_match)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotGUI()
    window.show()
    sys.exit(app.exec())


