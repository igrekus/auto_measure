import ast
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
        _ = self._measure_tune(token, param, secondary)
        self.result.set_secondary_params(self.secondaryParams)
        return True

    def _measure_tune(self, token, param, secondary):

        def find_peak_read_marker(first=False):
            sa.send('CALC:MARK1:MAX')

            if not mock_enabled:
                if first:
                    time.sleep(2)
                time.sleep(0.4)

            if first:
                sa.send('CALC:MARK1:MAX')
                if not mock_enabled:
                    time.sleep(1)

            freq = float(sa.query(':CALC:MARK1:X?'))
            pow_ = float(sa.query(':CALC:MARK1:Y?'))
            return freq, pow_

        src = self._instruments['Источник']
        sa = self._instruments['Анализатор']

        i_src_max = secondary['i_src_max'] * MILLI

        u_tune_min = secondary['u_vco_min']
        u_tune_max = secondary['u_vco_max']
        u_tune_step = secondary['u_vco_delta']
        i_tune_max = 10 * MILLI

        sa_f_start = secondary['sa_min'] * GIGA
        sa_f_stop = secondary['sa_max'] * GIGA
        sa_rlev = secondary['sa_rlev']
        sa_span = secondary['sa_span'] * MEGA

        u_src_drift_1 = secondary['u_src_drift_1']
        u_src_drift_2 = secondary['u_src_drift_2']
        u_src_drift_3 = secondary['u_src_drift_3']

        file_name = param['file']

        u_control_values = [round(x, 2) for x in np.arange(start=u_tune_min, stop=u_tune_max + 0.002, step=u_tune_step)]
        u_drift_values = [u for u in [u_src_drift_1, u_src_drift_2, u_src_drift_3] if u]

        # region main measure
        # TODO set source according to the source model
        src.send(f'APPLY p6v,{u_src_drift_1}V,{i_src_max}A')
        src.send(f'APPLY p25v,{u_control_values[0]}V,{i_tune_max}A')

        sa.send(f'DISP:WIND:TRAC:Y:RLEV {sa_rlev}')
        # sa.send(f'DISP:WIND:TRAC:X:OFFS {0}Hz')
        # sa.send(f'DISP:WIND:TRAC:Y:RLEV:OFFS {0}db')
        sa.send(f':SENS:FREQ:STAR {sa_f_start}Hz')
        sa.send(f':SENS:FREQ:STOP {sa_f_stop}Hz')
        sa.send(':CAL:AUTO OFF')
        sa.send(':CALC:MARK1:MODE POS')

        src.send('OUTP ON')

        if mock_enabled:
            with open('./mock_data/4.75-5.25-0.txt', mode='rt', encoding='utf-8') as f:
                index = 0
                mocked_raw_data = ast.literal_eval(''.join(f.readlines()))

        offset = defaultdict(dict)
        if isfile(file_name):
            print(f'found {file_name}, load offsets')
            tmp = pd.read_excel(file_name, engine='openpyxl').to_dict('records')
            for row in tmp:
                offset[row['Vcc']][row['Vctr']] = (row['Freq offs'], row['Pow offs'])

        result = []
        for u_drift in u_drift_values:
            first = True
            for u_control in u_control_values:

                if token.cancelled:
                    src.send('OUTP OFF')
                    sa.send(':CAL:AUTO ON')
                    raise RuntimeError('measurement cancelled')

                src.send(f'APPLY p6v,{u_drift}V,{i_src_max}A')
                src.send(f'APPLY p25v,{u_control}V,{i_tune_max}A')

                if not mock_enabled:
                    time.sleep(1)

                # sa.send(f'DISP:WIND:TRAC:X:OFFS {0}Hz')
                # sa.send(f'DISP:WIND:TRAC:Y:RLEV:OFFS {0}db')
                x_off, y_off = offset.get(u_drift, {}).get(u_control, (0, 0))
                x_off = x_off * MEGA
                sa.send(f'DISP:WIND:TRAC:X:OFFS {x_off}Hz')
                sa.send(f'DISP:WIND:TRAC:Y:RLEV:OFFS {y_off}db')

                sa.send(f':SENS:FREQ:STAR {sa_f_start}Hz')
                sa.send(f':SENS:FREQ:STOP {sa_f_stop}Hz')

                if not mock_enabled:
                    time.sleep(0.4)

                read_f, read_p = find_peak_read_marker(first)
                first = False
                read_i = float(src.query('MEAS:CURR? p6v'))

                raw_point = {
                    'u_src': u_drift,
                    'u_control': u_control,
                    'read_f': read_f,
                    'read_p': read_p,
                    'read_i': read_i,
                }

                print('measured point:', raw_point)

                if mock_enabled:
                    raw_point = mocked_raw_data[index]
                    index += 1

                self._add_measure_point(raw_point)

                result.append(raw_point)

            if not mock_enabled:
                time.sleep(5)

        # with open('out.txt', mode='wt', encoding='utf-8') as out_file:
        #     out_file.write(str(result))

        offs_template = pd.DataFrame([{'Vcc': r['u_src'], 'Vctr': r['u_control'], 'Freq offs': 0, 'Pow offs': 0} for r in result])
        offs_template.to_excel('template.xlsx', engine='openpyxl', index=False)

        src.send('OUTPut OFF')
        sa.send(':CAL:AUTO ON')

        return result

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
