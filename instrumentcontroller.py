import ast
import random
import time

from collections import defaultdict
from os.path import isfile

import numpy as np
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

        file_name = param['file']

        rows = [
            [1, 0, 0],
            [1, 1, 1],
            [1, 2, 2],
            [1, 3, 3],
            [1, 4, 4],
            [1, 5, 5],
            [1, 6, 6],
            [1, 7, 7],
            [1, 8, 8],
            [1, 9, 9],

            [2, 0, 1],
            [2, 1, 2],
            [2, 2, 3],
            [2, 3, 4],
            [2, 4, 5],
            [2, 5, 6],
            [2, 6, 7],
            [2, 7, 8],
            [2, 8, 9],
            [2, 9, 10],

            [3, 0, 2],
            [3, 1, 3],
            [3, 2, 4],
            [3, 3, 5],
            [3, 4, 6],
            [3, 5, 7],
            [3, 6, 8],
            [3, 7, 9],
            [3, 8, 10],
            [3, 9, 11],
        ]
        for series, x, y in rows:

            if token.cancelled:
                raise RuntimeError('measurement cancelled')

            raw_point = {
                'series': series,
                'x': x,
                'y1': y,
                'y2': y,
                'y3': y,
                'y4': y,
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
