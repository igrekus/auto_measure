import ast
import random
import time

from collections import defaultdict
from os.path import isfile
from pathlib import Path

import numpy as np
import pandas
import pandas as pd

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from forgot_again.file import load_ast_if_exists, pprint_to_file

from instr.instrumentfactory import mock_enabled, SourceFactory, AnalyzerFactory
from measureresult import MeasureResult
from secondaryparams import SecondaryParams

GIGA = 1_000_000_000
MEGA = 1_000_000
KILO = 1_000
MILLI = 1 / 1_000

# + TODO fix harmonics .xlsx export
# TODO add separate offset settings for x2 and x3


class InstrumentController(QObject):
    pointReady = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        addrs = load_ast_if_exists('instr.ini', default={
            'Анализатор': 'GPIB1::18::INSTR',
            'Источник': 'GPIB1::3::INSTR',
        })

        self.requiredInstruments = {
            'Анализатор': AnalyzerFactory(addrs['Анализатор']),
            'Источник': SourceFactory(addrs['Источник']),
        }

        self.deviceParams = load_ast_if_exists('devices.ini', default={
            'ГУН': {
                'file': 'input.xlsx',
            },
        })

        self.secondaryParams = SecondaryParams(required={
            'sep_4': ['', {'value': None}],
            'u_src_drift_1': [
                'Uп1=',
                {'start': 0.0, 'end': 10.0, 'step': 0.5, 'value': 4.7, 'suffix': ' В'}
            ],
            'u_src_drift_2': [
                'Uп2=',
                {'start': 0.0, 'end': 10.0, 'step': 0.5, 'value': 5.0, 'suffix': ' В'}
            ],
            'u_src_drift_3': [
                'Uп3=',
                {'start': 0.0, 'end': 10.0, 'step': 0.5, 'value': 5.3, 'suffix': ' В'}
            ],
            'i_src_max': [
                'Iп.макс=',
                {'start': 0.0, 'end': 500.0, 'step': 1.0, 'value': 50.0, 'suffix': ' мА'}
            ],
            'sep_1': ['', {'value': None}],
            'u_vco_min': [
                'Uупр.мин.=',
                {'start': 0.0, 'end': 30.0, 'step': 0.5, 'decimals': 2, 'value': 0.0, 'suffix': ' В'}
            ],
            'u_vco_max': [
                'Uупр.макс.=',
                {'start': 0.0, 'end': 30.0, 'step': 0.5, 'decimals': 2, 'value': 10.0, 'suffix': ' В'}
            ],
            'u_vco_delta': [
                'ΔUупр=',
                {'start': 0.0, 'end': 30.0, 'step': 0.5, 'decimals': 2, 'value': 1.0, 'suffix': ' В'}
            ],
            'sep_2': ['', {'value': None}],
            'sa_min': [
                'Start=',
                {'start': 0.0, 'end': 30.0, 'step': 0.5, 'value': 1.0, 'suffix': ' ГГц'}
            ],
            'sa_max': [
                'Stop=',
                {'start': 0.0, 'end': 30.0, 'step': 0.5, 'value': 1.0, 'suffix': ' ГГц'}
            ],
            'sa_rlev': [
                'Ref lev=',
                {'start': -30.0, 'end': 30.0, 'step': 1.0, 'value': 10.0, 'suffix': ' дБ'}
            ],
            'sa_span': [
                'Span=',
                {'start': 0.0, 'end': 30000.0, 'step': 1.0, 'value': 50.0, 'suffix': ' МГц'}
            ],
        })
        self.secondaryParams.load_from_config('params.ini')

        self._instruments = dict()
        self.found = False
        self.present = False
        self.hasResult = False

        self.result = MeasureResult()

    def __str__(self):
        return f'{self._instruments}'

    # region connections
    def connect(self, addrs):
        print(f'searching for {addrs}')
        for k, v in addrs.items():
            self.requiredInstruments[k].addr = v
        self.found = self._find()

    def _find(self):
        self._instruments = {
            k: v.find() for k, v in self.requiredInstruments.items()
        }
        return all(self._instruments.values())

    def check(self, token, params):
        print(f'call check with {token} {params}')
        device, secondary = params
        self.present = self._check(token, device, secondary)
        print('sample pass')

    def _check(self, token, device, secondary):
        print(f'launch check with {self.deviceParams[device]} {self.secondaryParams}')
        self._init()
        return True
    # endregion

    # region initialization
    def _clear(self):
        self.result.clear()

    def _init(self):
        self._instruments['Источник'].send('*RST')
        self._instruments['Источник'].send('OUTP OFF')
        self._instruments['Анализатор'].send('*RST')
    # endregion

    def measure(self, token, params):
        print(f'call measure with {token} {params}')
        device, _ = params
        try:
            self.result.set_secondary_params(self.secondaryParams)
            self._measure(token, device)
            # self.hasResult = bool(self.result)
            self.hasResult = True  # TODO HACK
        except RuntimeError as ex:
            print('runtime error:', ex)

    def _measure(self, token, device):
        param = self.deviceParams[device]
        secondary = self.secondaryParams.params
        print(f'launch measure with {token} {param} {secondary}')

        self._clear()
        self._do_measure(token, param, secondary)
        self.result.set_secondary_params(self.secondaryParams)
        return True

    def _do_measure(self, token, param, secondary):
        src = self._instruments['Источник']
        sa = self._instruments['Анализатор']

        file_name1 = Path('./tables/plot1.xlsx')
        file_name2 = Path('./tables/plot2.xlsx')
        file_name3 = Path('./tables/plot3.xlsx')
        file_name4 = Path('./tables/plot4.xlsx')

        df1 = pandas.read_excel(file_name1)
        df2 = pandas.read_excel(file_name2) if file_name2.is_file() else pandas.DataFrame()
        df3 = pandas.read_excel(file_name3) if file_name3.is_file() else pandas.DataFrame()
        df4 = pandas.read_excel(file_name4) if file_name4.is_file() else pandas.DataFrame()

        rows = len(df1)

        for index in range(rows):

            if token.cancelled:
                raise RuntimeError('measurement cancelled')

            raw_point = {
                'series1': df1[df1.columns[0]][index],
                'x1': df1[df1.columns[1]][index],
                'y1': df1[df1.columns[2]][index],

                'series2': '' if df2.empty else df2[df2.columns[0]].get(index, 0),
                'x2': 0 if df2.empty else df2[df2.columns[1]].get(index, 0),
                'y2': 0 if df2.empty else df2[df2.columns[2]].get(index, 0),

                'series3': '' if df3.empty else df3[df3.columns[0]].get(index, 0),
                'x3': 0 if df3.empty else df3[df3.columns[1]].get(index, 0),
                'y3': 0 if df3.empty else df3[df3.columns[2]].get(index, 0),

                'series4': '' if df4.empty else df4[df4.columns[0]].get(index, 0),
                'x4': 0 if df4.empty else df4[df4.columns[1]].get(index, 0),
                'y4': 0 if df4.empty else df4[df4.columns[2]].get(index, 0),
            }

            print('measured point:', raw_point)

            self._add_measure_point(raw_point)
            time.sleep(0.1)

    def _add_measure_point(self, data):
        print('measured point:', data)
        self.result.add_point(data)
        self.pointReady.emit()

    def saveConfigs(self):
        pprint_to_file('params.ini', self.secondaryParams.params)

    @pyqtSlot(dict)
    def on_secondary_changed(self, params):
        self.secondaryParams.params = params

    @property
    def status(self):
        return [i.status for i in self._instruments.values()]
