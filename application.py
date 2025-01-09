#! /bin/python3
import sys
import os
import datetime
import psutil
import sqlalchemy
from PySide6 import QtCore, QtWidgets
from sqlalchemy.types import BigInteger
from sqlalchemy.schema import Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

class Base(DeclarativeBase):
    pass

class Profiling(Base):
    __tablename__ = 'profiling'

    time: Mapped[datetime.datetime] = mapped_column(primary_key = True)
    cpu: Mapped[float]
    ram_available = Column('ram_available', BigInteger)
    ram_total = Column('ram_total', BigInteger)
    disk_available = Column('disk_available', BigInteger)
    disk_total = Column('disk_total', BigInteger)

class GUI(QtWidgets.QWidget):
    def __init__(self, cpu_percent, ram_available, ram_total, disk_available, disk_total):
        super().__init__()

        self.cpu_label = QtWidgets.QLabel(self.format_cpu(cpu_percent))
        self.ram_label = QtWidgets.QLabel(self.format_memory(ram_available, ram_total, True))
        self.drive_label = QtWidgets.QLabel(self.format_memory(disk_available, disk_total))

        self.start_recording_button = QtWidgets.QPushButton('Начать запись')
        self.start_recording_button.clicked.connect(self.start_recording)
        
        self.stop_recording_button = QtWidgets.QPushButton('Остановить')
        self.stop_recording_button.clicked.connect(self.stop_recording)

        self.recording_timer = QtCore.QElapsedTimer()
        self.recording_timer_label = QtWidgets.QLabel('00:00:00', alignment = QtCore.Qt.AlignCenter)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.cpu_label)
        self.layout.addWidget(self.ram_label)
        self.layout.addWidget(self.drive_label)
        self.layout.addWidget(self.start_recording_button)
        self.layout.addWidget(self.stop_recording_button)
        self.layout.addWidget(self.recording_timer_label)

        self.stop_recording()

    def format_cpu(self, cpu_percent):
        return f'ЦП: {cpu_percent}'

    def format_elapsed_time(self):
        time = QtCore.QTime.fromMSecsSinceStartOfDay(self.recording_timer.elapsed())
        return time.toString()

    def format_memory(self, available, total, is_ram = False):
        memory_type = 'ПЗУ'
        if is_ram:
            memory_type = 'ОЗУ'
        return f'{memory_type}: {self.scale_memory(available)}/{self.scale_memory(total)}'

    def scale_memory(self, amount):
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        while amount > 1024 and unit_index < len(units):
            amount /= 1024
            unit_index += 1
        return f'{amount:.3f}{units[unit_index]}'

    def recording(self):
        return self.is_recording

    def start_recording(self):
        self.start_recording_button.hide()
        self.stop_recording_button.show()
        self.recording_timer_label.show()
        self.recording_timer.start()
        self.recording_timer_label.setText('00:00:00')

        self.is_recording = True

    def stop_recording(self):
        self.stop_recording_button.hide()
        self.start_recording_button.show()
        self.recording_timer_label.hide()

        self.is_recording = False
    
    def update(self, cpu_percent, ram_available, ram_total, disk_available, disk_total):
        self.cpu_label.setText(self.format_cpu(cpu_percent))
        self.ram_label.setText(self.format_memory(ram_available, ram_total, True))
        self.drive_label.setText(self.format_memory(disk_available, disk_total))

        if self.recording():
            self.recording_timer_label.setText(self.format_elapsed_time())

class Application(QtWidgets.QApplication):
    def __init__(self, period, db_url):
        super().__init__(['app'])
        
        self.engine = sqlalchemy.create_engine(db_url)
        Base.metadata.create_all(self.engine)


        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        self.gui = GUI(psutil.cpu_percent(), ram.available, ram.total, disk.free, disk.total)
        self.gui.show()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(period * 1000)

    def update(self):
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu = psutil.cpu_percent()
        if self.gui.recording():
            session = Session(self.engine)
            db_entry = Profiling(time=datetime.datetime.now(),
                                cpu = cpu,
                                ram_available = ram.available,
                                ram_total = ram.total,
                                disk_available = disk.free,
                                disk_total = disk.total)
            session.add(db_entry)
            session.commit()
        self.gui.update(psutil.cpu_percent(), ram.available, ram.total, disk.free, disk.total)



if __name__ == '__main__':
    period = os.environ.get('PERIOD_SECS', '')
    if len(period) == 0:
        period = 1
    else:
        try:
            period = float(period)
        except:
            print('failed to parse update period in PERIOD_SECS environment variable')
            sys.exit(1)

    db_url = os.environ.get('DATABASE_URL', '')
    if len(db_url) == 0:
        print('DATABASE_URL environment variable must contain url for connecting to database')
        sys.exit(1)

    app = Application(period, db_url)
    sys.exit(app.exec())
