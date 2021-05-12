#!/usr/bin/env python3

import os
import sys
import time
import json
from collections import OrderedDict
import glob



from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QLabel, QFileDialog, QComboBox, QGraphicsPixmapItem, QDesktopWidget
from PyQt5.QtGui import QPixmap


# Because I use a "trick" to hide items of a QComboBox through its QListView,
# scrolling on a normal QComboBox lets me select items that are hidden, which is
# not desirable. So we override the class to prevent that.
class MyQComboBox(QComboBox):
    def wheelEvent(self, event):
        increment = 1 if event.angleDelta().y() < 0 else -1
        index = self.currentIndex()+increment
        if not (0 <= index < self.count()): return
        lv = self.view()
        while lv.isRowHidden(index) and 0 < index < self.count()-1:
            index += increment
        # If we got out of the loop and new index is hidden, we are on a hidden boundary item, so don't increment.
        if not lv.isRowHidden(index):
            self.setCurrentIndex(index)


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('mainwindow.ui', self)   # Load the .ui file

        # Place window in the center of the screen, and make it a bit smaller
        screenRect = QDesktopWidget().availableGeometry()
        windowRect = QRect()
        windowRect.setSize(screenRect.size()*0.75)
        windowRect.moveCenter(screenRect.center())
        self.setGeometry(windowRect)

        # Data
        self.mainFolder = ""
        self.configFile = ""
        self.defaultConfigFile = "sweep.txt"
        self.paramDict = OrderedDict()     # Holds current values of parameters to display
        self.fullParamDict = OrderedDict()     # Holds all possible values of each parameter
        self.allParamNames = []
        self.paramControlType = "combobox"   # "slider" or "combobox"
        self.comboBox_noneChoice = "--None--"
        self.xaxis = self.comboBox_noneChoice
        self.yaxis = self.comboBox_noneChoice
        self.filePattern = ""
        self.currentDir = ""

        # View
        self.paramControlWidgetList = []
        # Set up X and Y axis comboboxes
        self.gridLayout_display.addWidget(QLabel("X axis"), 1, 0)
        self.gridLayout_display.addWidget(QLabel("Y axis"), 2, 0)
        self.comboBox_xaxis = MyQComboBox()
        self.comboBox_yaxis = MyQComboBox()
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        self.gridLayout_display.addWidget(self.comboBox_xaxis, 1, 1)
        self.gridLayout_display.addWidget(self.comboBox_yaxis, 2, 1)

        self.scene = QtWidgets.QGraphicsScene()
        # self.graphicsView.scale(1,-1) # Flip the y axis, but it also flips images
        self.graphicsView.setScene(self.scene)
        self.show() # Show the GUI

        # Connect widgets
        self.lineEdit_mainFolder.textChanged.connect(self.mainFolder_changed)
        self.lineEdit_configFile.textChanged.connect(self.configFile_changed)
        self.lineEdit_filePattern.textChanged.connect(self.filePattern_changed)
        self.pushButton_mainFolder.pressed.connect(self.mainFolder_browse)
        self.pushButton_configFile.pressed.connect(self.configFile_browse)
        self.pushButton_clearLog.pressed.connect(self.log_clear)
        self.comboBox_xaxis.currentTextChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_yaxis.currentTextChanged.connect(self.comboBoxAxis_changed)


        # This changes the limit of the current view, ie what we see of the scene through the widget.
        # s = 100
        # self.graphicsView.fitInView(-s, -s, s, s, Qt.KeepAspectRatio)

        # The scene rectangle defines the extent of the scene, and in the view's case,
        # this means the area of the scene that you can navigate using the scroll bars.
        # If the view is larger than the provided rect, it doesn't change anything.
        # If the provided rect is larger than the view, it will add scrollbars to see the entire rectangle
        # self.graphicsView.setSceneRect(-500, -500, 1000, 1000)

        # Commands to change the widget size. They need to be called after self.show(), otherwise the widget size
        # is the default (100,30).
        # self.graphicsView.setFixedSize(100, 100)  # Changes the size of the widget
        # self.print(str(self.graphicsView.size()))   # Prints the size of the widget, not the scene bounding box coordinates
        # self.print(str(self.graphicsView.viewport().size()))    # Prints the size of the widget, not the scene bounding box coordinates

        # DEBUG
        self.lineEdit_mainFolder.setText("/home/matthieu/Work/Postdoc-UBC/Projects/trajectory_inference/DGCG_scRNAseq/examples/results_reprog_umap_2d_ss10__sig_ab_multistart")
        time.sleep(0.5)
        self.lineEdit_filePattern.setText("iter_001_insertion.png")
        # self.lineEdit_filePattern.setText("iter_*_insertion.png[-1]")


    def resizeEvent(self, event):   # This is an overloaded function
        QtWidgets.QMainWindow.resizeEvent(self, event)
        # Redraw when window is resized
        self.draw_graphics()

    def print(self,txt):
        self.text_log.appendPlainText(txt)

    def log_clear(self):
        self.text_log.clear()

    def mainFolder_browse(self):
        dir = str(QFileDialog.getExistingDirectory(self, "Select directory"))
        if dir:
            self.mainFolder = dir
        self.lineEdit_mainFolder.setText(self.mainFolder)

    def mainFolder_changed(self, path):
        # Check if it's a valid folder
        if not os.path.isdir(path):
            self.lineEdit_mainFolder.setStyleSheet("color: red;")
            self.mainFolder = ""
            self.draw_graphics()
            return
        self.lineEdit_mainFolder.setStyleSheet("color: black;")
        self.mainFolder = path
        # Check if there is a config file
        if os.path.isfile(os.path.join(self.mainFolder,self.defaultConfigFile)):
            self.lineEdit_configFile.setText(os.path.join(self.mainFolder,self.defaultConfigFile))
        else:
            self.print("No config file 'sweep.txt' found in %s. Please provide it manually."%self.mainFolder)
            return
        # Redraw
        self.draw_graphics()

    def configFile_browse(self):
        # file = str(QFileDialog.getOpenFileUrl(self, "Select file..."))
        file = QFileDialog.getOpenFileName(self, "Select file...")[0]
        if file:
            self.configFile = file
        self.lineEdit_configFile.setText(self.configFile)

    def configFile_invalid(self):
        self.lineEdit_configFile.setStyleSheet("color: red;")
        self.fullParamDict = {}
        self.paramDict = {}
        self.paramControlWidgetList.clear()
        # Delete all parameter control widgets
        # https://stackoverflow.com/a/13103617/4195725
        for i in reversed(range(self.gridLayout_paramControl.count())):
            self.gridLayout_paramControl.itemAt(i).widget().setParent(None)
        # Reset comboboxes
        self.comboBox_xaxis.clear()
        self.comboBox_yaxis.clear()
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        # Redraw
        self.draw_graphics()

    def configFile_changed(self, path):
        # Check if it's a valid file
        if not os.path.isfile(path):
            self.configFile_invalid()
            return
        self.lineEdit_configFile.setStyleSheet("color: black;")
        self.configFile = path
        # Read parameters from file and keep their order
        try:
            self.fullParamDict = json.load(open(self.configFile, 'r'), object_pairs_hook=OrderedDict)
        except:
            self.print("Error: the config file should be a json file")
            self.configFile_invalid()
            return
        # Get list of all parameter names
        self.allParamNames = list(self.fullParamDict.keys())
        # Populate the parameter controls
        self.populate_parameterControls()
        # Populate the axis comboboxes
        self.comboBox_xaxis.addItems(self.allParamNames)
        self.comboBox_yaxis.addItems(self.allParamNames)
        # Redraw
        self.draw_graphics()

    def populate_parameterControls(self):
        for i, (param,values) in enumerate(self.fullParamDict.items()):
            values = self.fullParamDict[param]
            textWidget = controlWidget = None
            if self.paramControlType == "combobox":
                textWidget = QLabel(param)
                controlWidget = QComboBox()
                controlWidget.addItems([str(v) for v in values])
            else:
                print("Not implemented")
            self.paramControlWidgetList.append(controlWidget)
            self.gridLayout_paramControl.addWidget(textWidget, i, 0)
            self.gridLayout_paramControl.addWidget(controlWidget, i, 1)
            # Connect signals
            self.paramControlWidgetList[i].currentIndexChanged.connect(self.paramControl_changed)
            # Initialize paramDict with first value of each parameter
            self.paramDict[param] = values[0]

    def comboBoxAxis_changed(self, text):
        #  If xaxis has changed
        #   If xaxis is a parameter other than None:
        #   - Remove param from paramDict, the control widgets and the combobox of yaxis
        #   If previous value was a parameter other than None:
        #   - Restore the previous param to paramDict, the control widgets and the combobox of yaxis
        #   Finally, store the new selection in xaxis
        #  Else if yaxis has change
        #   Vice versa

        def update_xyComboBox(combo_current, prev_param, combo_other):
            # If the new selection is not None, hide it where necessary
            param = combo_current.currentText()
            if param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(param)
                self.paramDict[param] = None
                self.paramControlWidgetList[param_index].setEnabled(False)
                combo_other.view().setRowHidden(param_index+1, True)
            # If the previous selection was not None, restore it where necessary
            if prev_param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(prev_param)
                self.paramDict[prev_param] = self.fullParamDict[prev_param][self.paramControlWidgetList[param_index].currentIndex()]  # Restore to previous value
                self.paramControlWidgetList[param_index].setEnabled(True)
                combo_other.view().setRowHidden(param_index+1, False)

        if self.sender() is self.comboBox_xaxis:
            update_xyComboBox(self.comboBox_xaxis, self.xaxis, self.comboBox_yaxis)
            self.xaxis = self.comboBox_xaxis.currentText()
        elif self.sender() is self.comboBox_yaxis:
            update_xyComboBox(self.comboBox_yaxis, self.yaxis, self.comboBox_xaxis)
            self.yaxis = self.comboBox_yaxis.currentText()

        # Redraw
        self.draw_graphics()

    def filePattern_changed(self, pattern):
        self.filePattern = pattern
        # Redraw
        self.draw_graphics()

    # @QtCore.pyqtSlot()
    def paramControl_changed(self, index):
        # Identify the sender
        id_sender = self.paramControlWidgetList.index(self.sender())
        # Get parameter name
        param = self.allParamNames[id_sender]
        # Change current parameter
        self.paramDict[param] = self.fullParamDict[param][index]
        # Redraw
        self.draw_graphics()

    def draw_graphics(self):
        # Clear the scene before drawing
        self.scene.clear()
        # Check if any information is missing
        if not self.mainFolder or not self.paramDict or not self.filePattern:
            return
        alldirs = [os.path.basename(f) for f in os.scandir(self.mainFolder) if f.is_dir()]
        dirs = alldirs
        # Find all dirs that match all parameters
        for param, value in self.paramDict.items():
            dirs = [d for d in dirs if param+str(value) in d]
        # Check that there is only one left
        if len(dirs) == 0:
            self.print("Error: no folder matches the set of parameters")
            return
        if len(dirs) > 1:
            self.print("Error: multiple folders match the set of parameters:",dirs)
            return
        self.currentDir = dirs[0]

        # Check if file exists
        file = os.path.join(self.mainFolder,self.currentDir,self.filePattern)
        if not os.path.isfile(file):
            self.print("Error: no file in the folder matches the pattern.")
            return

        # Draw the images
        img = QGraphicsPixmapItem(QPixmap(file))
        self.scene.addItem(img)
        # img = QPixmap(file)
        # self.scene.addPixmap(img)

        # Readjust the view
        height = img.pixmap().size().height()
        width = img.pixmap().size().width()
        self.graphicsView.fitInView(0, 0, width, height, Qt.KeepAspectRatio)



if __name__ == '__main__':

    app = QtWidgets.QApplication(sys.argv) # Create an instance of QtWidgets.QApplication
    window = Ui() # Create an instance of our class
    app.exec_() # Start the application

