#!/usr/bin/env python3
import csv
import os
import sys
import time
import json
import io

import PyQt5.QtDesigner
import numpy as np
from collections import OrderedDict
import glob
import re
import argparse

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize, QSizeF, QLineF
from PyQt5.QtWidgets import QGraphicsView, QLabel, QFileDialog, QComboBox, QGraphicsPixmapItem, QDesktopWidget, QGraphicsTextItem, QPushButton, QGroupBox, QFrame
from PyQt5.QtGui import QPixmap, QPen, QColor, QImage, QPainter, QFont

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

if __name__ == "__main__":
    from common import *
else:
    from .common import *

# TODO
#  - Prevent users from loading sweep file (and result file) if mainfolder is not valid (grey/hide widgets out?)
#  - Add automatic file naming when saving
#  - In grid mode, select a subset of values to plot
#  - PDF support?
#  - Make the Size and Notes group boxes collapsible
#  - Add a mode to plot scalar results with up to varying parameters (using matplotlib)
#  - Integrate boilerplate code of non-swept parameters in the module
#  - In the Save part, above the path field, add one checkbox per parameter that adds/removes its value to the end
#    of the filename, no need to rewrite the parameter names next to the checkboxes, a title and tiptools are enough.
#    Also, an option to toggle the title would be nice as well
#  - Add a title also when in result matrix mode

# BUG
#  - When in nested result matrix mode, updates are very slow, find out why
#  - When in nested result matrix mode, clicking on text size changes it twice (signal received twice?)


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


# TODO: Either replace a QGroupBox in the UI programatically to this class,
#  or find a way to add it as a widget in QtDesigner
# class CollapsibleGroupBox(QFrame):
class CollapsibleGroupBox(QtWidgets.QWidget, PyQt5.QtDesigner.QDesignerContainerExtension):
    def __init__(self, parent):
        super(CollapsibleGroupBox, self).__init__(parent)
        # Attributes
        self.collapsed = False
        self.title = 'CollapsibleGroupBox'
        layout = QtWidgets.QVBoxLayout()
        # Widgets
        self.button = QPushButton()
        self.button.setFlat(True)
        self.button.setStyleSheet('text-align: left;')
        self.setTitle(self.title)
        self.button.pressed.connect(self.toggle_collapsed)
        layout.addWidget(self.button)

        self.groupbox = QGroupBox()
        layout.addWidget(self.groupbox)

        self.setLayout(layout)

    def isContainer(self):
        return True

    def setTitle(self,title):
        self.title = title
        self.setButtonText()

    def setButtonText(self):
        if self.collapsed:
            self.button.setText("\u25B8 %s"%self.title)
        else:
            self.button.setText("\u25BE %s"%self.title)

    def toggle_collapsed(self):
        self.collapsed = ~self.collapsed
        self.setButtonText()
        if self.collapsed:
            self.groupbox.hide()
        else:
            self.groupbox.show()


# Make basic types iterable to print them more easily
QSize.__iter__ = lambda s: iter([s.width(),s.height()])
QSizeF.__iter__ = lambda s: iter([s.width(),s.height()])
QPoint.__iter__ = lambda s: iter([s.x(),s.y()])
QPointF.__iter__ = lambda s: iter([s.x(),s.y()])


# Class for a matplotlib figure
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        # self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


# Scene where we can zoom and move around with the mouse
class MyQGraphicsView(QGraphicsView):
    def __init__(self, parent):
        super(MyQGraphicsView, self).__init__(parent)
        self.zoom = 1
        self.m_originX = 0
        self.m_originY = 0

    # Adapted from https://blog.automaton2000.com/2014/04/mouse-centered-zooming-in-qgraphicsview.html
    def wheelEvent(self, event):
        if event.angleDelta().x() == 0:
            pos = event.pos()
            posf = self.mapToScene(pos)
            scaleFactor = 0.5
            scale = 1 + event.angleDelta().y()/360*scaleFactor
            self.scale(scale, scale)
            w = self.viewport().width()
            h = self.viewport().height()
            wf = self.mapToScene(QPoint(w-1, 0)).x() - self.mapToScene(QPoint(0,0)).x()
            hf = self.mapToScene(QPoint(0, h-1)).y() - self.mapToScene(QPoint(0,0)).y()
            lf = posf.x() - pos.x() * wf / w
            tf = posf.y() - pos.y() * hf / h
            # try to set viewport properly
            self.ensureVisible(lf, tf, wf, hf, 0, 0)
            newPos = self.mapToScene(pos)
            # It seems I don't need to do that:
            # # readjust according to the still remaining offset/drift
            # # I don't know how to do this any other way
            # self.ensureVisible(QRectF(QPointF(lf, tf) - newPos + posf, QSizeF(wf, hf)), 0, 0)
            event.accept()

    # Taken from https://stackoverflow.com/a/35865262/4195725
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Store original position.
            self.m_originX = event.x()
            self.m_originY = event.y()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            oldP = self.mapToScene(self.m_originX, self.m_originY)
            newP = self.mapToScene(event.pos())
            translation = newP - oldP
            self.setTransformationAnchor(QGraphicsView.NoAnchor)
            self.translate(translation.x(), translation.y())
            self.m_originX = event.x()
            self.m_originY = event.y()


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(os.path.join(os.path.dirname(__file__),'mainwindow.ui'), self)   # Load the .ui file

        # Place window in the center of the screen, and make it a bit smaller
        screenRect = QDesktopWidget().availableGeometry()
        windowRect = QRect()
        windowRect.setSize(screenRect.size()*0.75)
        windowRect.moveCenter(screenRect.center())
        self.setGeometry(windowRect)

        # Handle behavior of the left toolbar initially and when resizing
        # https://forum.qt.io/topic/13869/how-to-make-the-size-of-a-widget-in-a-qsplitter-fixed-when-resizing-the-qsplitter/8
        self.widget_leftToolbar.setMinimumSize(150,0)  # First value is min width of the toolbar
        self.splitter.setSizes([260, 1000])  # Initially, toolbar is 260. The second value has no effect.
        self.splitter.setStretchFactor(0,0)  # When resizing the window, don't stretch the toolbar
        self.splitter.setStretchFactor(1,1)  # When resizing the window, stretch the view widget
        # Revert what is in the .ui file since it's there just for the preview to look like the real thing.
        self.widget_leftToolbar.setMaximumSize(10000,10000)

        # Split between notes and log
        self.text_log.setMinimumSize(0,40)  # Second value is min width of the log
        self.splitter_notes_log.setSizes([1000, 40])  # Initially, notes are as big as possible and log is 40.

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
        self.resultName = self.comboBox_noneChoice
        self.resultsCSV = ""
        self.allResultNames = []
        self.filePattern = ""
        self.currentImages = None
        self.currentImagePaths = None
        self.resultArray = None
        self.notesFile = ""
        self.notesFileContent = ""
        self.notesFileNames = ["notes.md","notes.txt"]

        # Output
        self.defaultSaveFileName = "output.png"
        self.lineEdit_saveFile.setText(self.defaultSaveFileName)

        # View
        self.comboBox_filePattern.hide()
        self.progressBar.hide()
        self.paramControlWidgetList = []
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_result.addItem(self.comboBox_noneChoice)
        self.imageSpacing = [0,0]   # x and y spacing between images
        self.imageCrop = [0,0,0,0]  # how much to crop images in percentage [left,bottom,right,top]
        self.doubleSpinBox_cropList = [self.doubleSpinBox_cropL,self.doubleSpinBox_cropB,
                                       self.doubleSpinBox_cropR,self.doubleSpinBox_cropT]
        self.imageFrameLineWidth = 0
        self.imageFrameColor = "black"
        self.labelRelSize = 0
        self.resultFontWeight = self.spinBox_resultFontWeight.value()
        self.resultFontColor = "black"
        self.resultFontRelSize = 0
        self.resultFontBackground = False
        self.resultStrFormatter = lambda x: str(x)
        self.sceneRect = None
        self.viewRect = None
        self.zoom = 1
        self.pushButton_groupbox_save.setStyleSheet('text-align: left;')
        self.prevTimeScandir = 1
        self.resultMatrixCmap = "viridis"

        # Add X2 axis and Y2 axis
        self.X2_label = QLabel("X2 Axis")
        self.Y2_label = QLabel("Y2 Axis")
        self.comboBox_x2axis = MyQComboBox()
        self.comboBox_y2axis = MyQComboBox()
        self.x2axis = self.comboBox_noneChoice
        self.y2axis = self.comboBox_noneChoice
        self.comboBox_x2axis.addItem(self.x2axis)
        self.comboBox_y2axis.addItem(self.y2axis)
        self.displayAxisLabelLayout.addWidget(self.X2_label)
        self.displayAxisLabelLayout.addWidget(self.Y2_label)
        self.displayAxisLayout.addWidget(self.comboBox_x2axis)
        self.displayAxisLayout.addWidget(self.comboBox_y2axis)
        # Show matrix plot widgets
        self.X2_label.setVisible(False)
        self.comboBox_x2axis.setVisible(False)
        self.Y2_label.setVisible(False)
        self.comboBox_y2axis.setVisible(False)

        self.horizontalWidget_cmap.setVisible(False)
        self.checkBox_uniqueCmap.setVisible(False)
        self.label_cmap.setVisible(False)
        self.lineEdit_cmap.setText(self.resultMatrixCmap)

        self.scene = QtWidgets.QGraphicsScene()
        # self.graphicsView.scale(1,-1) # Flip the y axis, but it also flips images
        self.graphicsView.setScene(self.scene)
        self.show() # Show the GUI

        # Toggle off groupboxes (has to be done after self.show())
        self.groupbox_save_toggled()

        # Connect widgets
        self.lineEdit_mainFolder.textChanged.connect(self.mainFolder_changed)
        self.lineEdit_configFile.textChanged.connect(self.configFile_changed)
        self.lineEdit_filePattern.editingFinished.connect(self.filePattern_changed)
        self.comboBox_filePattern.currentIndexChanged.connect(self.filePattern_changed)
        self.pushButton_mainFolder.pressed.connect(self.mainFolder_browse)
        self.pushButton_configFile.pressed.connect(self.configFile_browse)
        self.pushButton_clearLog.pressed.connect(self.log_clear)
        self.comboBox_xaxis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_yaxis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_x2axis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_y2axis.currentIndexChanged.connect(self.comboBoxAxis_changed)
        self.comboBox_result.currentIndexChanged.connect(self.comboBoxResult_changed)
        [w.valueChanged.connect(self.crop_changed) for w in self.doubleSpinBox_cropList]
        self.spinBox_spacingX.valueChanged.connect(self.spacing_changed)
        self.spinBox_spacingY.valueChanged.connect(self.spacing_changed)
        self.spinBox_frameLineWidth.valueChanged.connect(self.frameLineWidth_changed)
        self.lineEdit_frameColor.textChanged.connect(self.frameColor_changed)
        self.spinBox_labelRelSize.valueChanged.connect(self.labelRelSize_changed)
        self.lineEdit_resultFontColor.textChanged.connect(self.resultFontColor_changed)
        self.spinBox_resultFontWeight.valueChanged.connect(self.resultFontWeight_changed)
        self.pushButton_resultBackground.toggled.connect(self.resultFontBackground_changed)
        self.spinBox_resultFontRelSize.valueChanged.connect(self.resultFontRelSize_changed)
        self.pushButton_saveFileBrowse.pressed.connect(self.saveFile_browse)
        self.pushButton_saveFile.pressed.connect(self.saveFile_save)
        self.doubleSpinBox_ImageReduction.valueChanged.connect(self.imageReduction_changed)
        self.plainTextEdit_notes.installEventFilter(self)
        self.pushButton_groupbox_save.pressed.connect(self.groupbox_save_toggled)
        self.checkBox_resultMatrix.stateChanged.connect(self.resultMatrix_checked)
        self.lineEdit_resultFormat.textChanged.connect(self.resultFormat_changed)
        self.checkBox_uniqueCmap.stateChanged.connect(self.uniqueCmap_checked)
        self.lineEdit_cmap.textChanged.connect(self.cmap_changed)

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

        # Deal with parameters
        parser = argparse.ArgumentParser(description="SweetSweep: a viewer for parameter sweep results", epilog="")
        parser.add_argument("sweep_dir", type=str, nargs='?', default="", help="Input directory (optional) where the sweep results are (all experiments directories and the 'sweep.txt' file)")
        args = parser.parse_args()
        # If the folder name is provided, put it in the corresponding text box.
        if args.sweep_dir:
            self.lineEdit_mainFolder.setText(args.sweep_dir)

        # DEBUG
        # self.lineEdit_mainFolder.setText("")
        # time.sleep(0.5)
        # self.lineEdit_filePattern.setText("")
        # self.filePattern_changed()
        return

    def eventFilter(self, object, event):  # This is an overloaded function
        # If we focus out of the notes
        if object == self.plainTextEdit_notes and event.type() == QtCore.QEvent.FocusOut:
            self.window().save_notes_file()

        # pass the event on to the parent class
        return super(Ui, self).eventFilter(object, event)

    def resizeEvent(self, event):  # This is an overloaded function
        QtWidgets.QMainWindow.resizeEvent(self, event)
        # Redraw when window is resized
        self.draw_graphics(reload_images=False)

    def print(self,*txt):
        # Convert everything into a str and join it to make a single string,
        # because this method only accepts one string
        self.text_log.appendPlainText(" ".join([str(t) for t in txt]))

    def log_clear(self):
        self.text_log.clear()

    def mainFolder_browse(self):
        dir = str(QFileDialog.getExistingDirectory(self, "Select directory", os.path.dirname(self.mainFolder.rstrip("/"))))
        if dir:
            self.mainFolder = dir
        self.lineEdit_mainFolder.setText(self.mainFolder)

    def mainFolder_changed(self, path):
        # Check if it's a valid folder
        if not os.path.isdir(path):
            self.lineEdit_mainFolder.setStyleSheet("color: red;")
            self.mainFolder = ""
            self.configFile_invalid()
            self.draw_graphics()
            return
        self.lineEdit_mainFolder.setStyleSheet("color: black;")
        self.mainFolder = path
        # Check if there is a config file
        if os.path.isfile(os.path.join(self.mainFolder,self.defaultConfigFile)):
            if os.path.join(self.mainFolder,self.defaultConfigFile) == self.lineEdit_configFile.text():
                # If the config file is the same as previously, setText() won't fire the changed() signal,
                # which won't call this function, so we call it manually.
                self.configFile_changed(self.lineEdit_configFile.text())
            else:
                self.lineEdit_configFile.setText(os.path.join(self.mainFolder, self.defaultConfigFile))
        else:
            self.print("No config file 'sweep.txt' found in %s. Please provide it manually."%self.mainFolder)
            return
        # No need to redraw here since it's alreay done by configFile_changed() in all cases

    def find_notes_file(self):
        """
        This function tries to find the notes file.
        If it does, it will set it in self.notesFile
        :return: nothing
        """
        # First, look in self.notesFile in case a filename was provided in the config file
        if self.notesFile:
            if os.path.isfile(self.notesFile):
                return
            self.print("Couldn't find the notes file '%s'"%os.path.basename(self.notesFile))
        # If not, look for pre-defined names.
        for name in self.notesFileNames:
            f = os.path.join(self.mainFolder, name)
            if os.path.isfile(f):
                self.notesFile = f
                return
        # If none are found
        self.notesFile = ""

    def load_notes_file(self):
        # Search for the notes file
        self.find_notes_file()
        if not self.notesFile:
            return
        # If found, load it
        self.groupBox_notes.setTitle("Notes: %s"%os.path.basename(self.notesFile))
        with open(self.notesFile, 'r') as f:
            text = f.read()
            self.plainTextEdit_notes.blockSignals(True)
            self.plainTextEdit_notes.setPlainText(text)
            self.plainTextEdit_notes.blockSignals(False)
            self.notesFileContent = text
        return

    def save_notes_file(self):
        text = self.plainTextEdit_notes.toPlainText()
        if not self.notesFile and not text or not self.mainFolder:
            return
        # If text has changed compared to file content
        if text != self.notesFileContent:
            # If no notes file existed, create one.
            if not self.notesFile:
                self.notesFile = os.path.join(self.mainFolder,self.notesFileNames[0])
                self.groupBox_notes.setTitle("Notes: %s"%self.notesFileNames[0])
            with open(self.notesFile, 'w') as f:
                f.write(text)
                self.notesFileContent = text
        return

    def groupbox_save_toggled(self):
        if self.groupBox_save.isVisible():
            self.pushButton_groupbox_save.setText("\u25B8 Save")
            self.groupBox_save.hide()
        else:
            self.pushButton_groupbox_save.setText("\u25BE Save")
            self.groupBox_save.show()
        return

    def configFile_browse(self):
        # file = str(QFileDialog.getOpenFileUrl(self, "Select file..."))
        file = QFileDialog.getOpenFileName(self, "Select file...",self.mainFolder)[0]
        if file:
            self.configFile = file
        self.lineEdit_configFile.setText(self.configFile)

    def configFile_invalid(self):
        # Reset data
        self.lineEdit_configFile.setStyleSheet("color: red;")
        self.fullParamDict = {}
        self.paramDict = {}
        self.allParamNames = []
        self.paramControlWidgetList.clear()
        self.allResultNames = []
        self.resultArray = None
        self.notesFile = ""
        self.notesFileContent = ""

        # Reset widgets
        self.plainTextEdit_notes.clear()
        self.groupBox_notes.setTitle("Notes")
        # Delete all parameter control widgets
        # https://stackoverflow.com/a/13103617/4195725
        for i in reversed(range(self.gridLayout_paramControl.count())):
            self.gridLayout_paramControl.itemAt(i).widget().setParent(None)
        # Reset comboboxes
        self.comboBox_xaxis.blockSignals(True)
        self.comboBox_yaxis.blockSignals(True)
        self.comboBox_x2axis.blockSignals(True)
        self.comboBox_y2axis.blockSignals(True)
        self.comboBox_result.blockSignals(True)
        self.comboBox_filePattern.blockSignals(True)
        self.comboBox_xaxis.clear()
        self.comboBox_yaxis.clear()
        self.comboBox_x2axis.clear()
        self.comboBox_y2axis.clear()
        self.comboBox_result.clear()
        self.comboBox_filePattern.clear()
        self.comboBox_xaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_yaxis.addItem(self.comboBox_noneChoice)
        self.comboBox_x2axis.addItem(self.comboBox_noneChoice)
        self.comboBox_y2axis.addItem(self.comboBox_noneChoice)
        self.comboBox_result.addItem(self.comboBox_noneChoice)
        self.comboBox_filePattern.addItem(self.comboBox_noneChoice)
        self.comboBox_xaxis.blockSignals(False)
        self.comboBox_yaxis.blockSignals(False)
        self.comboBox_x2axis.blockSignals(False)
        self.comboBox_y2axis.blockSignals(False)
        self.comboBox_result.blockSignals(False)
        self.comboBox_filePattern.blockSignals(False)
        self.xaxis = self.comboBox_noneChoice
        self.yaxis = self.comboBox_noneChoice
        self.resultName = self.comboBox_noneChoice

        # Redraw
        self.draw_graphics()

    def configFile_changed(self, path):
        # Check if it's a valid file
        if not os.path.isfile(path):
            self.configFile_invalid()
            return
        # First clear all parameter controls and axis comboboxes
        self.configFile_invalid()
        # Then redo everything with the new config file
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
        self.allParamNames = [param for param in self.fullParamDict.keys() if not param.startswith("viewer_")]

        # Check if there are viewer parameters
        if "viewer_cropLBRT" in self.fullParamDict:
            self.set_cropLBRT(self.fullParamDict["viewer_cropLBRT"])
            del self.fullParamDict["viewer_cropLBRT"]
        if "viewer_filePattern" in self.fullParamDict:
            if isinstance(self.fullParamDict["viewer_filePattern"], list):
                self.lineEdit_filePattern.hide()
                self.comboBox_filePattern.show()
                self.comboBox_filePattern.clear()
                self.comboBox_filePattern.addItems(self.fullParamDict["viewer_filePattern"])
            else:
                self.comboBox_filePattern.hide()
                self.lineEdit_filePattern.show()
                self.lineEdit_filePattern.setText(self.fullParamDict["viewer_filePattern"])
                self.filePattern = self.fullParamDict["viewer_filePattern"]
            del self.fullParamDict["viewer_filePattern"]
            # No need to call self.filePattern_changed because we already set self.filePattern
            # and later call draw_graphics()
        if "viewer_resultsCSV" in self.fullParamDict:
            self.resultsCSV = self.fullParamDict["viewer_resultsCSV"]
            # Read CSV
            self.read_resultsCSV(os.path.join(os.path.dirname(path), self.resultsCSV))
            del self.fullParamDict["viewer_resultsCSV"]
        if "viewer_notesFile" in self.fullParamDict:
            self.notesFile = os.path.join(self.mainFolder,self.fullParamDict["viewer_notesFile"])
            del self.fullParamDict["viewer_notesFile"]

        # Get the notes file
        self.load_notes_file()

        # Populate the parameter controls
        self.populate_parameterControls()
        # Populate the axis comboboxes
        self.comboBox_xaxis.addItems(self.allParamNames)
        self.comboBox_yaxis.addItems(self.allParamNames)
        self.comboBox_x2axis.addItems(self.allParamNames)
        self.comboBox_y2axis.addItems(self.allParamNames)
        # Populate result combobox if a csv was read
        if self.resultArray is not None:
            self.comboBox_result.addItems(["exp_id",] + self.allResultNames)
        # Redraw
        self.draw_graphics()


    def populate_parameterControls(self):
        for i, (param,values) in enumerate(self.fullParamDict.items()):
            textWidget = controlWidget = None
            if self.paramControlType == "combobox":
                textWidget = QLabel(param)
                controlWidget = QComboBox()
                controlWidget.addItems([val2str(v) for v in values])
            else:
                print("Not implemented")
            self.paramControlWidgetList.append(controlWidget)
            self.gridLayout_paramControl.addWidget(textWidget, i, 0)
            self.gridLayout_paramControl.addWidget(controlWidget, i, 1)
            # Connect signals
            self.paramControlWidgetList[i].currentIndexChanged.connect(self.paramControl_changed)
            # Initialize paramDict with first value of each parameter
            self.paramDict[param] = [values[0]]

    def comboBoxAxis_changed(self, index):
        #  If xaxis has changed
        #   If xaxis is a parameter other than None:
        #   - Remove param from paramDict, the control widgets and the combobox of yaxis
        #   If previous value was a parameter other than None:
        #   - Restore the previous param to paramDict, the control widgets and the combobox of yaxis
        #   Finally, store the new selection in xaxis
        #  Else if yaxis has change
        #   Vice versa

        def update_axisComboBox(combo_current, prev_param, combo_other):
            # If the new selection is not None, hide it where necessary
            param = combo_current.currentText()
            if param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(param)
                self.paramDict[param] = self.fullParamDict[param]
                self.paramControlWidgetList[param_index].setEnabled(False)
                for other in combo_other:
                    other.view().setRowHidden(param_index+1, True)
            # If the previous selection was not None, restore it where necessary
            if prev_param != self.comboBox_noneChoice:
                param_index = self.allParamNames.index(prev_param)
                self.paramDict[prev_param] = [self.fullParamDict[prev_param][self.paramControlWidgetList[param_index].currentIndex()]]  # Restore to previous value
                self.paramControlWidgetList[param_index].setEnabled(True)
                for other in combo_other:
                    other.view().setRowHidden(param_index+1, False)

        if self.sender() is self.comboBox_xaxis:
            update_axisComboBox(self.comboBox_xaxis, self.xaxis, [self.comboBox_yaxis,self.comboBox_x2axis,self.comboBox_y2axis])
            self.xaxis = self.comboBox_xaxis.currentText()
        elif self.sender() is self.comboBox_yaxis:
            update_axisComboBox(self.comboBox_yaxis, self.yaxis, [self.comboBox_xaxis,self.comboBox_x2axis,self.comboBox_y2axis])
            self.yaxis = self.comboBox_yaxis.currentText()
        elif self.sender() is self.comboBox_x2axis:
            update_axisComboBox(self.comboBox_x2axis, self.x2axis, [self.comboBox_xaxis,self.comboBox_yaxis,self.comboBox_y2axis])
            self.x2axis = self.comboBox_x2axis.currentText()
        elif self.sender() is self.comboBox_y2axis:
            update_axisComboBox(self.comboBox_y2axis, self.y2axis, [self.comboBox_xaxis,self.comboBox_yaxis,self.comboBox_x2axis])
            self.y2axis = self.comboBox_y2axis.currentText()

        # Unique colormap checkbox
        if self.x2axis == self.y2axis == self.comboBox_noneChoice:
            self.checkBox_uniqueCmap.hide()
        else:
            self.checkBox_uniqueCmap.show()

        # Redraw
        self.draw_graphics()

    def comboBoxResult_changed(self, index):
        self.resultName = self.comboBox_result.currentText()

        # Deal with the result format field
        if index != 0: self.checkResultFormat()
        else: self.lineEdit_resultFormat.setStyleSheet("color: black;")

        # Redraw
        self.draw_graphics(reload_images=False, reset_view=False)
        return

    def filePattern_changed(self, index=0):
        if self.comboBox_filePattern.isVisible():
            # If pattern hasn't changed, no need to redraw
            if self.comboBox_filePattern.itemText(index) == self.filePattern:
                return
            self.filePattern = self.comboBox_filePattern.itemText(index)
        else:
            # If pattern hasn't changed, no need to redraw
            if self.lineEdit_filePattern.text() == self.filePattern:
                return
            self.filePattern = self.lineEdit_filePattern.text()
        # Redraw
        self.draw_graphics()

    # @QtCore.pyqtSlot()
    def paramControl_changed(self, index):
        # Identify the sender
        id_sender = self.paramControlWidgetList.index(self.sender())
        # Get parameter name
        param = self.allParamNames[id_sender]
        # Change current parameter
        self.paramDict[param] = [self.fullParamDict[param][index]]
        # Redraw
        self.draw_graphics()

    def crop_changed(self, value):
        # Update the variable
        self.imageCrop = [w.value()/100 for w in self.doubleSpinBox_cropList]
        self.draw_graphics(reload_images=False, reset_view=False)

    def set_cropLBRT(self, cropLBRT):
        self.imageCrop = cropLBRT
        # Block signals
        [w.blockSignals(True) for i, w in enumerate(self.doubleSpinBox_cropList)]
        [w.setValue(cropLBRT[i]) for i,w in enumerate(self.doubleSpinBox_cropList)]
        [w.blockSignals(False) for i, w in enumerate(self.doubleSpinBox_cropList)]
        # Call the slot only once
        self.crop_changed(0)

    def spacing_changed(self, value):
        # Update the variable
        self.imageSpacing = [self.spinBox_spacingX.value(),self.spinBox_spacingY.value()]
        self.draw_graphics(reload_images=False, reset_view=False)

    def getImageCroppingRect(self, pixmap):
        return QRect(int(self.imageCrop[0] * pixmap.width()), int(self.imageCrop[3] * pixmap.height()),
                     int((1 - self.imageCrop[2]) * pixmap.width() - self.imageCrop[0] * pixmap.width()),
                     int((1 - self.imageCrop[1]) * pixmap.height() - self.imageCrop[3] * pixmap.height()))

    def frameLineWidth_changed(self, value):
        self.imageFrameLineWidth = value
        self.draw_graphics(reload_images=False, reset_view=False)

    def frameColor_changed(self, text):
        self.imageFrameColor = text
        self.draw_graphics(reload_images=False, reset_view=False)

    def labelRelSize_changed(self, value):
        self.labelRelSize = value
        self.draw_graphics(reload_images=False, reset_view=False)

    def resultFontWeight_changed(self, value):
        self.resultFontWeight = value
        self.draw_graphics(reload_images=False, reset_view=False)

    def resultFontColor_changed(self, text):
        self.resultFontColor = text
        self.draw_graphics(reload_images=False, reset_view=False)

    def resultFontBackground_changed(self, state):
        self.resultFontBackground = state > 0
        self.draw_graphics(reload_images=False, reset_view=False)

    def resultFontRelSize_changed(self, value):
        self.resultFontRelSize = value
        self.draw_graphics(reload_images=False, reset_view=False)

    def resultFormat_changed(self, text):
        if self.resultName != self.comboBox_noneChoice:
            self.checkResultFormat()
        self.draw_graphics(reload_images=False, reset_view=False)

    def checkResultFormat(self):
        result_format = self.lineEdit_resultFormat.text()
        self.resultStrFormatter = lambda x: str(x)
        self.lineEdit_resultFormat.setStyleSheet("color: black;")
        # Check if result format is valid
        # https://realpython.com/python-formatted-output/#the-format_spec-component
        if re.match('^{.*}$', result_format):  # Format must start with { and end with }
            try:
                # Try to format the result as requested
                result_format.format(self.resultArray[self.resultName][0])
                self.resultStrFormatter = lambda s: result_format.format(s)
            except Exception:
                self.lineEdit_resultFormat.setStyleSheet("color: red;")
                pass
        elif result_format:  # If field is not empty but didn't match
            self.lineEdit_resultFormat.setStyleSheet("color: red;")

    def resultMatrix_checked(self, state):
        self.comboBox_filePattern.setDisabled(state)
        # Show/hide X2 and Y2 axes
        self.X2_label.setVisible(state)
        self.comboBox_x2axis.setVisible(state)
        self.Y2_label.setVisible(state)
        self.comboBox_y2axis.setVisible(state)
        self.label_cmap.setVisible(state)
        self.horizontalWidget_cmap.setVisible(state)
        self.draw_graphics()

    def uniqueCmap_checked(self, state):
        self.draw_graphics()

    def cmap_changed(self, txt):
        try:
            matplotlib.cm.get_cmap(txt)
            self.resultMatrixCmap = txt
            self.lineEdit_cmap.setStyleSheet("color: black;")
            self.draw_graphics()
        except Exception:
            self.lineEdit_cmap.setStyleSheet("color: red;")
            pass

    def read_resultsCSV(self, csv_path):
        with open(csv_path, newline='') as csv_file:
            csv_reader = csv.reader(csv_file)
            header = next(csv_reader)
            csv_all = [row for row in csv_reader]
        csv_dict = {row[0]: row[1:] for row in csv_all if row}
        # Replace values in redundant experiments if any
        if "src_exp_id" in header:
            for row in csv_all:
                src_exp_id = row[1]
                if src_exp_id != '-1':
                    row += csv_dict[src_exp_id][len(row) - 1:]
        # Rewrite CSV file in a string
        imputed_csv_file = "\n".join([",".join(row) for row in [header] + csv_all])
        try:
            self.resultArray = np.genfromtxt(io.StringIO(imputed_csv_file), delimiter=',', names=True, dtype=None, encoding=None)
            # self.resultArray = np.genfromtxt(csv_path, delimiter=',', names=True, dtype=None, encoding=None)
            self.allResultNames = [name for name in self.resultArray.dtype.names if name not in (self.allParamNames + ["exp_id"])]
        except Exception as e:
            self.print("Exception:", e)
            self.print("Unable to read result file '%s'." % self.resultsCSV)
            self.allResultNames = []

    def draw_graphics(self, reload_images=True, reset_view=True):
        """
        Draw the scene
        :param reload_images: Whether we need to reload displayed images from the disk
        :param reset_view: Whether to reset the view (which could have been changed e.g. by zooming in)
        :return: nothing
        """

        # print("Draw!")
        # Clear the scene before drawing
        self.scene.clear()
        # Check if any information is missing
        if not self.mainFolder or not self.paramDict or not self.filePattern:
            return

        # Get number of images on each axis
        xrange = self.paramDict[self.xaxis] if self.xaxis != self.comboBox_noneChoice else [None]
        yrange = self.paramDict[self.yaxis] if self.yaxis != self.comboBox_noneChoice else [None]
        x2range = self.paramDict[self.x2axis] if self.x2axis != self.comboBox_noneChoice else [None]
        y2range = self.paramDict[self.y2axis] if self.y2axis != self.comboBox_noneChoice else [None]
        nValuesX = len(xrange)
        nValuesY = len(yrange)
        nValuesX2 = len(x2range)
        nValuesY2 = len(y2range)

        # If we only show the result matrix, overwrite reload_images
        plot_resultMatrix = self.checkBox_resultMatrix.isChecked()
        if plot_resultMatrix: reload_images = False

        if reload_images or self.currentImagePaths is None:

            # For when reading files has latency (e.g. mounted folder)
            if self.prevTimeScandir > 0.5:
                self.progressBar.show()
                self.progressBar.setValue(50)
                # For some unknown reason, the bar doesn't show up when I change the viewed file, but I don't have
                # parameters on X or Y axis. If I do, then it shows up. So I have to repaint manually.
                self.progressBar.repaint()

            t_start = time.time()
            alldirs = [os.path.basename(f) for f in os.scandir(self.mainFolder) if f.is_dir()]
            t_end = time.time()
            self.prevTimeScandir = t_end-t_start
            self.progressBar.hide()  # Hide even if it wasn't shown

            used_dirs = alldirs.copy()
            # Find dirs that match all single parameters
            for param, value in self.paramDict.items():
                if len(value) == 1:
                    used_dirs = [d for d in used_dirs if re.search(re.escape("_"+param+val2str(value[0]))+"(_|$)", d)]
            self.currentImagePaths = np.full((nValuesY,nValuesX), "", dtype=object)
            self.currentImages = np.full((nValuesY, nValuesX), None, dtype=object)
            self.matchedPatterns = np.full((nValuesY, nValuesX),"",dtype=object)
            for i, ival in enumerate(yrange):
                for j, jval in enumerate(xrange):
                    # Find the correct folder
                    dirs = used_dirs.copy()
                    if ival is not None: dirs = [d for d in dirs if re.search(re.escape(self.yaxis+val2str(ival))+"(_|$)", d)]
                    if jval is not None: dirs = [d for d in dirs if re.search(re.escape(self.xaxis+val2str(jval))+"(_|$)", d)]
                    if len(dirs) == 0: self.print("Error: no folder matches the set of parameters"); continue
                    if len(dirs) > 1: self.print("Error: multiple folders match the set of parameters:", *dirs); continue
                    currentDir = dirs[0]

                    # Check if file exists
                    # Check if it's a glob pattern
                    if "*" in self.filePattern:
                        bracketMatch = re.search("\[.*\]", self.filePattern)
                        if bracketMatch is None or bracketMatch.end() != len(self.filePattern):
                            self.print("Error: When using glob pattern (with '*'), you must also specify an index enclosed in "
                                       "brackets at the end of the pattern, like so: 'image_*.png[-1]' (which asks for "
                                       "the last matching file).")
                            return
                        indexStr = bracketMatch.group()[1:-1]
                        try:
                            index = int(indexStr)
                        except ValueError:
                            self.print("Error: The content of the brackets in the file pattern must be a number.")
                            return
                        fullPattern = os.path.join(self.mainFolder, currentDir, self.filePattern[:bracketMatch.start()] + self.filePattern[bracketMatch.end():])
                        files = sorted(glob.glob(fullPattern))
                        if not (-len(files) <= index < len(files)):
                            continue
                        file = files[index]
                        # Get the part of the filename that corresponds to the * in the pattern
                        self.matchedPatterns[i,j] = file
                        for f in fullPattern.split("*"):
                            self.matchedPatterns[i,j] = self.matchedPatterns[i,j].replace(f, "")
                    else:
                        file = os.path.join(self.mainFolder, currentDir, self.filePattern)
                        if not os.path.isfile(file):
                            continue
                    self.currentImagePaths[i,j] = file

        # If we didn't find any images, stop drawing
        if np.all(self.currentImagePaths == "") and not plot_resultMatrix:
            self.print("Error: no file in the folder(s) matches the pattern.")
            return


        # If we need to show results
        if self.resultName != self.comboBox_noneChoice:
            # Precompute bool array that allows to find results values for a given set of parameters,
            # but for parameters that are neither in x or y axis.
            axis_list = [self.xaxis, self.yaxis]
            if plot_resultMatrix: axis_list += [self.x2axis, self.y2axis]
            non_axis_params = [name for name in self.allParamNames if name not in axis_list]
            if len(non_axis_params) == 0:
                non_axis_bool_array = np.ones(self.resultArray.shape,dtype=bool)
            else:
                # When a param has values with different types (e.g. num and str), it must be stored as the same type in resultArray.
                # So for comparing it with what's in paramDict, we need to use the same type as the one used in resultArray.
                non_axis_bool_array = np.logical_and.reduce([self.resultArray[p] == self.resultArray.dtype[p].type(self.paramDict[p][0]) for p in non_axis_params])

        # If display result matrix
        if plot_resultMatrix:
            # If no result selected
            if self.resultName == self.comboBox_noneChoice:
                self.print("ERROR: Select a result to plot")
            # If the selected result is not a number (e.g. a str), we can't plot a matrix for it
            elif not np.issubdtype(self.resultArray.dtype[self.resultName],np.number):
                self.print("ERROR: Cannot plot matrix for non-numeric data.")
            else:
                # Check color
                if not matplotlib.colors.is_color_like(self.resultFontColor):
                    self.resultFontColor = "black"
                # Check text background
                text_bbox = {"facecolor": 'white', "linewidth": 0, "pad": 1} if self.resultFontBackground else None

                # Create the figure
                # canvas = MplCanvas(self, width=7*np.cbrt(nValuesX2), height=7*np.cbrt(nValuesY2), dpi=500)
                canvas = MplCanvas(self, width=nValuesX*nValuesX2, height=nValuesY*nValuesY2, dpi=500)
                # canvas = MplCanvas(self, width=7, height=7, dpi=500)
                # ax = canvas.axes
                fig = canvas.figure

                # Draw a border around the figure.
                # fig.patch.set_linewidth(10)
                # fig.patch.set_edgecolor('blue')
                # print(canvas.get_width_height())

                # # Only for subplots
                # matplotlib.rcParams["axes.edgecolor"] = "blue"
                # matplotlib.rcParams["axes.linewidth"] = 3

                rcFontSize = 4 + 3*max(nValuesX2, nValuesY2) + self.labelRelSize
                font = {'size': rcFontSize} # 'weight': 'bold',
                matplotlib.rc('font', **font)

                # Create matrix of results
                # If some values are missing (e.g. sweep not finished)
                resultMatrix_dtype = type(self.resultArray[0][self.resultName])
                if np.sum(non_axis_bool_array) < nValuesX * nValuesY:
                    self.print("WARNING: Missing some result values.")
                    # Changing array to float to be able to replace missing values with NaNs
                    resultMatrix_dtype = float
                resultMatrix = np.zeros((nValuesY, nValuesX), dtype=resultMatrix_dtype)

                vmin = vmax = None
                if self.checkBox_uniqueCmap.isChecked():
                    vmin = self.resultArray[non_axis_bool_array][self.resultName].min()
                    vmax = self.resultArray[non_axis_bool_array][self.resultName].max()

                # Do subplots if necessary
                for i2, i2val in enumerate(y2range):
                    for j2, j2val in enumerate(x2range):
                        ax = fig.add_subplot(nValuesY2,nValuesX2,i2*nValuesX2+j2+1)

                        # Plot text and fill resultMatrix
                        for i, ival in enumerate(yrange):
                            for j, jval in enumerate(xrange):
                                # Get corresponding result
                                bool_array = non_axis_bool_array.copy()
                                if self.xaxis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.xaxis] == self.resultArray[self.xaxis].dtype.type(jval))
                                if self.yaxis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.yaxis] == self.resultArray[self.yaxis].dtype.type(ival))
                                if self.x2axis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.x2axis] == self.resultArray[self.x2axis].dtype.type(j2val))
                                if self.y2axis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.y2axis] == self.resultArray[self.y2axis].dtype.type(i2val))

                                txt = None
                                if np.count_nonzero(bool_array) == 0: # the result is not in the csv, so don't display anything
                                    resultMatrix[i, j] = np.nan
                                    txt = ""
                                elif np.count_nonzero(bool_array) > 1:
                                    self.print("Warning: The set of parameters matches multiple experiments.")
                                elif np.count_nonzero(bool_array) == 1:
                                    # Get corresponding value in row
                                    resultMatrix[i, j] = self.resultArray[bool_array][self.resultName][0]
                                    txt = self.resultStrFormatter(resultMatrix[i, j])
                                # Plot text
                                ax.text(j, i, txt, va='center', ha='center', c=self.resultFontColor, bbox=text_bbox,
                                        fontsize=10+self.resultFontRelSize/2, fontweight=250*self.resultFontWeight)
                        # Plot matrix
                        im = ax.matshow(resultMatrix, cmap=self.resultMatrixCmap, vmin=vmin, vmax=vmax)
                        # Change axes, ticks and labels
                        xticklabels = xrange
                        yticklabels = yrange
                        xlabel = self.x2axis + "=" + val2str(j2val) + "\n" + self.xaxis if self.x2axis != self.comboBox_noneChoice else self.xaxis
                        ylabel = self.y2axis + "=" + val2str(i2val) + "\n" + self.yaxis if self.y2axis != self.comboBox_noneChoice else self.yaxis
                        if i2 != 0:
                            ax.tick_params(axis='x', top=False)  # Only top ticks for first row
                            xticklabels = []
                            xlabel = ""
                        if j2 != 0:
                            ax.tick_params(axis='y', left=False)  # Only left ticks for first column
                            yticklabels = []
                            ylabel = ""
                        ax.set_xticks(range(nValuesX))
                        ax.set_yticks(range(nValuesY))
                        ax.set_xticklabels(xticklabels)
                        ax.set_yticklabels(yticklabels)
                        ax.xaxis.set_label_position('top')
                        ax.tick_params(axis='x', bottom=False)  # Remove all bottom ticks
                        if self.xaxis != self.comboBox_noneChoice: ax.set_xlabel(xlabel)
                        if self.yaxis != self.comboBox_noneChoice: ax.set_ylabel(ylabel)

                        # Tighten everything
                        fig.tight_layout()
                        # fig.colorbar(im)  # Not necessary since we plot the exact values

                # # TODO: To get those right, start in a new python, make up some data, and plot it like you want it.
                # # Add suplabels
                # if self.x2axis != self.comboBox_noneChoice:
                #     # fig.supxlabel(self.x2axis)
                #     fig.text(x=0.5,y=0,s=self.x2axis)
                #     [fig.text(x=(j+1)/(nValuesX2+1), y=0, s=val) for j, val in enumerate(x2range)]
                #     # fig.text(x=0.5,y=0.99,s=self.x2axis)
                # if self.y2axis != self.comboBox_noneChoice:
                #     # fig.supylabel(self.y2axis)
                #     fig.text(x=-len(self.y2axis)/100,y=0.5,s=self.y2axis, ha="right")
                #     [fig.text(x=0, y=(i+1)/(nValuesY2+1), s=val) for i, val in enumerate(y2range)]

                # # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
                # toolbar = NavigationToolbar(canvas, self)
                # # Create a placeholder widget to hold our toolbar and canvas.
                # layout = QtWidgets.QVBoxLayout()
                # layout.addWidget(toolbar)
                # layout.addWidget(canvas)
                # widget = QtWidgets.QWidget()
                # widget.setLayout(layout)
                # self.scene.addWidget(widget)
                self.scene.addWidget(canvas)

        else:  # If display image matrix

            # Assume all image dimensions are those of the first valid image
            imIndex = np.argmax(self.currentImagePaths.flatten() != "")
            i,j = np.unravel_index(imIndex,self.currentImagePaths.shape)
            if reload_images:
                self.currentImages[i,j] = QPixmap(self.currentImagePaths[i,j])
            cropRect = self.getImageCroppingRect(self.currentImages[i,j])
            pc = self.currentImages[i,j].copy(cropRect)
            # Get image dimension after cropping
            imWidth = pc.width()
            imHeight = pc.height()

            # Get dimensions of the scene to compute font size
            viewSize = self.graphicsView.size()
            sceneSize = QSize(nValuesX*(imWidth+self.imageSpacing[0]), nValuesY*(imHeight+self.imageSpacing[1]))
            maxViewSize = max(viewSize.width(), viewSize.height())
            maxSceneSize = max(sceneSize.width(), sceneSize.height())
            # print("Image size:",sceneSize)
            # print("View size:",self.graphicsView.size())
            # print("Point size:",txt.font().pointSize())
            # It's very difficult to find a formula that gives a good font size in all situations, because it
            # depends on the size of the images, and the number of images (so the size of the drawing).
            # But for confortable viewing, it should also depend on how large the graphicsview widget is, even
            # though the content of that window should be agnostic to the size of the window we visualize it in.
            # fontSize = 60
            # fontSize = int(maxSceneSize/40)
            fontSize = int(maxSceneSize / maxViewSize * 20)
            # Spacing between labels and images
            # labelSpacing = max(imWidth,imHeight)/20
            labelSpacing = fontSize*0.75

            # Show a progress bar
            show_pbar = nValuesX*nValuesY > 1 and reload_images
            if show_pbar: self.progressBar.show()


            # Draw images and labels
            for i, ival in enumerate(yrange):
                for j, jval in enumerate(xrange):

                    # Update progress bar
                    if show_pbar: self.progressBar.setValue(int((i*nValuesX+j)/(nValuesX*nValuesY-1)*100))

                    # Compute image position and frame size
                    imagePos = QPointF(j * (imWidth + self.imageSpacing[0]), i * (imHeight + self.imageSpacing[1]))
                    frameRect = QRectF(imagePos,QSizeF(cropRect.size()))

                    # Draw existing images
                    if self.currentImagePaths[i,j]:
                        # Load the image
                        if reload_images:
                            self.currentImages[i,j] = QPixmap(self.currentImagePaths[i,j])
                            # print("Loading image",i,j)
                        # This way of drawing assumes all images have the size of the first image
                        # Crop the image
                        pc = self.currentImages[i,j].copy(cropRect)

                        # Draw the image
                        imageItem = QGraphicsPixmapItem(pc)
                        imageItem.setOffset(imagePos)
                        self.scene.addItem(imageItem)
                    # Draw placeholders where there are no images
                    else:
                        rect = QRectF(QPointF(),frameRect.size()*0.5)
                        rect.moveCenter(frameRect.center())
                        pen = QPen(QColor(self.imageFrameColor),5)
                        self.scene.addLine(QLineF(rect.topLeft(),rect.bottomRight()),pen)
                        self.scene.addLine(QLineF(rect.bottomLeft(),rect.topRight()),pen)

                    # Draw matched pattern if present
                    if self.matchedPatterns[i,j] != "":
                        textItem = QGraphicsTextItem()
                        textItem.setFont(QFont("Sans Serif", pointSize=fontSize+self.resultFontRelSize))
                        textItem.setPlainText(self.matchedPatterns[i,j])
                        # textBR = textItem.sceneBoundingRect()
                        textItem.setPos(imagePos)
                        self.scene.addItem(textItem)

                    # Draw top labels if X axis is not None
                    if jval is not None and i == 0:
                        textItem = QGraphicsTextItem()
                        textItem.setFont(QFont("Sans Serif", pointSize=fontSize + self.labelRelSize))
                        # textItem.setPlainText(self.xaxis+"= "+val2str(jval))
                        textItem.setPlainText(val2str(jval))
                        textBR = textItem.sceneBoundingRect()
                        # height/10 is the arbitary spacing that separates labels from images
                        # Subtract textBR.height() on Y so that the bottom of the text is always imHeight/10 from the image
                        textItem.setPos(imagePos + QPointF(imWidth/2 - textBR.width()/2, -labelSpacing - textBR.height()))
                        textItem.setTextWidth(imWidth)
                        self.scene.addItem(textItem)

                    # Draw left labels if Y axis is not None
                    if ival is not None and j == 0:
                        textItem = QGraphicsTextItem()
                        textItem.setFont(QFont("Sans Serif", pointSize=fontSize + self.labelRelSize))
                        # textItem.setPlainText(self.yaxis+"= "+val2str(ival))
                        textItem.setPlainText(val2str(ival))
                        textItem.setRotation(-90)
                        textBR = textItem.sceneBoundingRect()
                        textItem.setPos(imagePos + QPointF(-labelSpacing - textBR.width(), imHeight/2 + textBR.height()/2))
                        textItem.setTextWidth(imHeight)
                        self.scene.addItem(textItem)

                    # Draw the result if one is selected
                    if self.resultName != self.comboBox_noneChoice:
                        # Get row corresponding to the current set of parameters in result array
                        # It's probably faster to get it by exp_id, but this is fast enough for now, and it's more reliable
                        bool_array = non_axis_bool_array.copy()
                        if self.xaxis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.xaxis] == self.resultArray[self.xaxis].dtype.type(jval))
                        if self.yaxis != self.comboBox_noneChoice: bool_array = np.logical_and(bool_array,self.resultArray[self.yaxis] == self.resultArray[self.yaxis].dtype.type(ival))

                        # If np.count_nonzero(bool_array) == 0, the result is not in the csv, so don't display anything
                        if np.count_nonzero(bool_array) > 1:
                            self.print("Warning: The set of parameters matches multiple experiments.")
                        elif np.count_nonzero(bool_array) == 1:
                            # Get corresponding value in row
                            result_value_ij = self.resultStrFormatter(self.resultArray[bool_array][self.resultName][0])
                            # Print the text
                            resultTextItem = QGraphicsTextItem()
                            resultTextItem.setFont(QFont("Sans Serif", pointSize=fontSize+self.resultFontRelSize, weight=35*(self.resultFontWeight-1)))
                            resultTextItem.setDefaultTextColor(QColor(self.resultFontColor))
                            if self.resultFontBackground:
                                resultTextItem.setHtml("<div style='background:rgba(255, 255, 255, 100%);'>" + result_value_ij + "</div>")
                            else:
                                resultTextItem.setPlainText(result_value_ij)
                            resultTextItem.setPos(imagePos)
                            textBR = resultTextItem.sceneBoundingRect()
                            resultTextItem.setPos(imagePos + QPointF(imWidth/2 - textBR.width()/2, imHeight/2 - textBR.height()/2))
                            # resultTextItem.setPos(imagePos + QPointF(imWidth/2, imHeight/2))
                            # resultTextItem.setTextWidth(imWidth)
                            self.scene.addItem(resultTextItem)

                    # Draw frames
                    if self.imageFrameLineWidth != 0:
                        self.scene.addRect(frameRect,QPen(QColor(self.imageFrameColor),self.imageFrameLineWidth))

            # Draw top labels if X axis is not None
            if xrange[0] is not None:
                textItem = QGraphicsTextItem()
                textItem.setFont(QFont("Sans Serif", pointSize=fontSize + self.labelRelSize))
                textItem.setPlainText(self.xaxis)
                textBR = textItem.sceneBoundingRect()
                textPos = QPointF(nValuesX/2 * (imWidth + self.imageSpacing[0]), 0)
                textItem.setPos(textPos + QPointF(-textBR.width()/2, -4*labelSpacing - textBR.height()))
                textItem.setTextWidth(imWidth)
                self.scene.addItem(textItem)

            # Draw left labels if Y axis is not None
            if yrange[0] is not None:
                textItem = QGraphicsTextItem()
                textItem.setFont(QFont("Sans Serif", pointSize=fontSize + self.labelRelSize))
                textItem.setPlainText(self.yaxis)
                textItem.setRotation(-90)
                textBR = textItem.sceneBoundingRect()
                textPos = QPointF(0, nValuesY/2 * (imHeight + self.imageSpacing[1]))
                textItem.setPos(textPos + QPointF(-4*labelSpacing - textBR.width(), textBR.height()/2))
                textItem.setTextWidth(imHeight)
                self.scene.addItem(textItem)

            # Hide the progress bar
            if show_pbar: self.progressBar.hide()

        # Compute view rectangle
        self.sceneRect = self.scene.itemsBoundingRect()
        self.viewRect = QRectF(self.sceneRect)
        # self.scene.addRect(self.viewRect)  # Plot the view rectangle

        if not plot_resultMatrix:
            # Add main title
            textItem = QGraphicsTextItem()
            textItem.setFont(QFont("Sans Serif", pointSize=fontSize + self.labelRelSize))
            text = ""
            for param,value in self.paramDict.items():
                if len(value) == 1: text += param + "=" + val2str(value[0]) + ", "
            if text: text = text[:-2]   # Remove trailing ", " if not empty
            textItem.setPlainText(text)
            textBR = textItem.sceneBoundingRect()
            textItem.setPos(self.sceneRect.center() - QPointF(textBR.width()/2,
                            self.sceneRect.height()/2 + labelSpacing + textBR.height()))
            self.scene.addItem(textItem)

        # Recompute view rectangle
        self.sceneRect = self.scene.itemsBoundingRect()
        # self.scene.addRect(self.sceneRect)  # Plot the scene rectangle
        # Readjust the view
        if reset_view: self.graphicsView.fitInView(self.sceneRect, Qt.KeepAspectRatio)
        # Readjust the scrolling area
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        # Update show image size
        self.printImageSizesInLabel()

    def saveFile_browse(self):
        file = (QFileDialog.getSaveFileName(self, "Save view"))[0]
        if file:
            self.lineEdit_saveFile.setText(file)
        return

    def printImageSizesInLabel(self):
        sceneSize = self.scene.sceneRect().size()
        text = "Scene size:\t\t %dx%d\n"%(*sceneSize.toSize(),)
        outSize = (sceneSize*self.doubleSpinBox_ImageReduction.value()).toSize()
        text += "Output image size:\t %dx%d"%(*outSize,)
        self.label_imageSize.setText(text)

    def imageReduction_changed(self, value):
        self.printImageSizesInLabel()

    def saveFile_save(self):
        file = self.lineEdit_saveFile.text()
        # If file is a relative path, we save it in the input folder.
        if not file.startswith('/'):
            file = os.path.join(self.mainFolder,file)
        # Save the scene
        # From https://stackoverflow.com/a/11642517/4195725
        self.scene.clearSelection()
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        image = QImage((self.scene.sceneRect().size()*self.doubleSpinBox_ImageReduction.value()).toSize(),QImage.Format_ARGB32)
        # image.fill(Qt.transparent)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.scene.render(painter)
        image.save(file)
        del painter

        return


def start_viewer():
    app = QtWidgets.QApplication(sys.argv) # Create an instance of QtWidgets.QApplication
    window = Ui() # Create an instance of our class
    app.exec_() # Start the application


if __name__ == '__main__':

    start_viewer()
