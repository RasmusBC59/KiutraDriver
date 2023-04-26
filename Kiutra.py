import time
from typing import Any

from kiutra_api.api_client import KiutraClient
from kiutra_api.controller_interfaces import (
    ADRControl,
    ContinuousTemperatureControl,
    MagnetControl,
    SampleControl,
    HeaterControl,
    CryostatControl,
)
from qcodes import validators as vals
from qcodes.dataset import Measurement
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter, ParameterBase


class KiutraIns(Instrument):
    def __init__(self, name: str, address: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.host = address
        self.client = KiutraClient(self.host, 1006)
        self.sample_magnet = MagnetControl("sample_magnet", self.host)
        self.temperature_control = ContinuousTemperatureControl("temperature_control", self.host)
        self.adr_control = ADRControl("adr_control", self.host)
        self.sample_heater = HeaterControl("sample_heater", self.host)
        self.sample_loader = SampleControl("sample_loader", self.host)
        self.cryostat_control = CryostatControl("cryostat_control", self.host)
        print(self.client.query("cryostat.status"))

        self.add_parameter(
            "magnetic_field",
            label="Magnetic field",
            unit="T",
            parameter_class=MagneticField,
            vals=vals.Numbers(0.0, 4),
        )

        self.add_parameter(
            "magnetic_field_rate",
            label="Field Rate",
            unit="T/min",
            vals=vals.Numbers(0.01, 1.0),
            initial_value=0.1,
            set_cmd = lambda x: x
        )

        self.add_parameter(
            "temperature",
            label="Temperature",
            unit="K",
            parameter_class=TemperatureControl,
            vals=vals.Numbers(0.1, 300),
        )

        self.add_parameter(
            "temperature_rate",
            label="Temperature Rate",
            unit="K/min",
            vals=vals.Numbers(0.01, 4.0),
            initial_value=0.1,
            set_cmd = lambda x: x
        )

        # self.add_parameter(
        #     "sample_loader",
        #     label="Sample Loader",
        #     parameter_class=SampleLoader,
        # )

        self.add_parameter(
            "sample_magnet_power_on",
            label="Sample Magnet Power ON",
            get_cmd=self.sample_magnet.power_on,
        )

        self.add_parameter(
            "sample_magnet_power_off",
            label="Sample Magnet Power OFF",
            get_cmd=self.sample_magnet.power_off,
        )

        self.add_parameter(
            "sample_magnet_stable",
            label="Sample Magnet Stable",
            get_cmd=self.sample_magnet.stable_magnet,
        )

        self.add_parameter(
            "stable_temperature",
            label="Stable Temperature",
            vals=vals.String,
            get_cmd=self.temperature_control.stable_temperature,
        )

        self.add_parameter(
            "interrupt_temperature",
            label="Interrupt Temperature",
            vals=vals.String,
            get_cmd=self.temperature_control.interrupt_temp,
        )

        self.add_parameter(
            "interrupt_magnet",
            label="Interrupt Magnet",
            vals=vals.String,
            get_cmd=self.temperature_control.interrupt_magnet,
        )

        self.add_parameter(
            "interrupt_loader",
            label="Interrupt Loader",
            vals=vals.String,
            get_cmd=self.temperature_control.interrupt_loader,
        )

        self.add_parameter(
            "interrupt_heater",
            label="Interrupt Heater",
            vals=vals.String,
            get_cmd=self.temperature_control.interrupt_heater,
        )

        self.add_parameter(
            "heater_power",
            label="Heater Power",
            unit="W",
            vals=vals.Numbers(0, 1),
            get_cmd=self.sample_heater.power,
        )

        self.add_parameter(
            "heater_range",
            label="Heater Range",
            vals=vals.String,
            get_cmd=self.sample_heater.heater_range,
        )

        self.add_parameter(
            "reset_heater",
            label="Reset Heater",
            vals=vals.String,
            get_cmd=self.sample_heater.heater_reset,
        )

        self.add_parameter(
            "reset_temp_control",
            label="Reset Temperature Control",
            vals=vals.String,
            get_cmd=self.sample_heater.temp_reset,
        )

        self.add_parameter(
            "reset_sample_magnet",
            label="Reset Sample Magnet",
            vals=vals.String,
            get_cmd=self.sample_heater.magnet_reset,
        )       

        self.add_parameter(
            "reset_loader",
            label="Reset Loader",
            vals=vals.String,
            get_cmd=self.sample_heater.loader_reset,
        )

        self.add_parameter(
            "sample_load",
            label="Load Sample",
            vals=vals.String,
            get_cmd=self.sample_loader.load,
        )

        self.add_parameter(
            "sample_unload",
            label="Unload Sample",
            vals=vals.String,
            get_cmd=self.sample_loader.unload,
        )

        self.add_parameter(
            "vent_chamber",
            label="Vent Chamber",
            vals=vals.String,
            get_cmd=self.sample_loader.vent,
        )

        self.add_parameter(
            "evacuate_chamber",
            label="Evacuate Chamber",
            vals=vals.String,
            get_cmd=self.sample_loader.evac_chamber
        )

        self.add_parameter(
            "loader_blocks",
            label="Loader Blocks",
            vals=vals.String,
            get_cmd=self.sample_loader.load_blocks,
        )

        self.add_parameter(
            "temperature_blocks",
            label="Temperature Blocks",
            vals=vals.String,
            get_cmd=self.temperature_control.temp_blocks,
        )

        self.add_parameter(
            "magnet_blocks",
            label="Sample Magnet Blocks",
            vals=vals.String,
            get_cmd=self.sample_magnet.magnet_blocks,
        )

        self.add_parameter(
            "pressure",
            label="Pressure",
            vals=vals.Numbers(0, 1),
            get_cmd=self.cryostat_control.pressure,
        )

        self.add_parameter(
            "full_warmup",
            label="Full Warmup",
            vals=vals.String,
            get_cmd=self.cryostat_control.warmup_,
        )

        self.add_parameter(
            "discharge_magnets",
            label="Discharge Magnets",
            vals=vals.String,
            get_cmd=self.cryostat_control.discharge_magnets,
        )

        self.add_parameter(
            "close_baffles",
            label="Closes Baffles",
            vals=vals.String,
            get_cmd=self.cryostat_control.close_baff,
        )

        self.add_parameter(
            "open_baffles",
            label="Opens Baffles",
            vals=vals.String,
            get_cmd=self.cryostat_control.open_baff,
        )

        self.add_parameter(
            "close_gate",
            label="Closes Gate",
            vals=vals.String,
            get_cmd=self.cryostat_control.close_gate_,
        )

        self.add_parameter(
            "open_gate",
            label="Opens Gate",
            vals=vals.String,
            get_cmd=self.cryostat_control.open_gate_,
        )

        self.add_parameter(
            "cryostat_cooldown",
            label="Cryostat Cooldown",
            vals=vals.String,
            get_cmd=self.cryostat_control.full_cooldown,
        )

        self.add_parameter(
            "cooldown_progress",
            label="Cooldown Progress",
            vals=vals.String,
            get_cmd=self.cryostat_control.cooldown_progress,
        )

        self.add_parameter(
            "evacuate_cryostat",
            label="Evacuate Cryostat",
            vals=vals.String,
            get_cmd=self.cryostat_control.evacuate_cryostat,
        )

        self.add_parameter(
            "initialize_cryostat",
            label="Initialize Cryostat",
            vals=vals.String,
            get_cmd=self.cryostat_control.init_cryostat,
        )

def discharge_magnets(cryostat: object) -> str:
    cryostat.clear_magnets()
    return "Magnets are discharging"

def close_baff(cryostat: object) -> str:
    cryostat.close_baffles()
    return "Baffles are closing"

def open_baff(cryostat: object) -> str:
    cryostat.open_baffles()
    return "Baffles are opening"

def close_gate_(cryostat: object) -> str:
    cryostat.close_gate()
    return "Gate is closing"

def open_gate_(cryostat: object) -> str:
    cryostat.open_gate()
    return "Gate is opening"

def full_cooldown(cryostat: object) -> str:
    cryostat.cooldown()
    return "Cryostat cooling down"

def cooldown_progress(cryostat: object) -> str:
    return "Cooldown is %.1f percent done" % 100 * cryostat.detailed_progress

def evacuate_cryostat(cryostat: object) -> str:
    cryostat.evacuate()

def init_cryostat(cryostat: object) -> str:
    cryostat.initialize()

def warmup_(cryostat: object) -> str:
    cryostat.warmup()
    return "Warmup begun"

def load(sample_loader: object) -> str: # can the sample be loaded while the base is cold?
    sample_loader.load_sample()
    print("Kiutra has started loading the sample")
    while sample_loader.progress < 1: # check whether progress is given in percent or decimal
        print("Loading is %.0f completed" % 100 * sample_loader.progress)
        time.sleep(1)
    return "Loading complete"

def unload(sample_loader: object) -> str:
    sample_loader.unload_sample()
    print("Kiutra has started unloading the sample")
    while sample_loader.progress < 1: # check if progress is gives a meaningful number when unloading
        print("Unloading is %.0f completed" % 100 * sample_loader.progress)
        time.sleep(1)
    return "Unloading complete"

def vent(sample_loader: object) -> str:
    sample_loader.open_airlock()
    return "Airlock is being opened"

def evac_chamber(sample_loader: object) -> str:
    sample_loader.close_airlock()
    return "Airlock is being closed"

def load_blocks(sample_loader: object) -> str:
    if sample_loader.is_blocked == True:
        return sample_loader.is_blocked_by # check whether this is a callable or not
    else:
        return "No devices block the sample loader"
    
def temp_blocks(sample_temp: object) -> str:
    if sample_temp.is_blocked == True:
        return sample_temp.is_blocked_by # check whether this is a callable or not
    else:
        return "No devices block the temperature control"
    
def magnet_blocks(sample_magnet: object) -> str:
    if sample_magnet.is_blocked == True:
        return sample_magnet.is_blocked_by # check whether this is a callable or not
    else:
        return "No devices block the sample magnet operation"

def heater_range(sample_heater: object) -> str:
    return sample_heater.range

def heater_reset(sample_heater: object) -> str:
    sample_heater.reset
    return "Heater has been reset"

def magnet_reset(sample_magnet: object) -> str:
    sample_magnet.reset
    return "Sample magnet has been reset"

def temp_reset(temperature_control: object) -> str:
    temperature_control.reset
    return "Temperature Control has been reset"

def loader_reset(sample_loader: object) -> str:
    sample_loader.reset
    return "Sample loader has been reset"

def interrupt_temp(temperature_control: object) -> str:
    temperature_control.stop
    return "Temperature operation interrupted"

def interrupt_magnet(sample_magnet: object) -> str:
    sample_magnet.stop
    return "Sample magnet operation interrupted"

def interrupt_loader(sample_loader: object) -> str:
    sample_loader.stop
    return "Sample loader operation interrupted"

def interrupt_heater(sample_heater: object) -> str:
    sample_heater.stop
    return "Sample heater operation interrupted"

def power_on(magnet: object) -> str:
    magnet.on()
    return "Magnet power supply has been switched on"

def power_off(magnet: object) -> str:
    magnet.off()
    return "Magnet power supply has been switched off"

def stable_magnet(magnet: object) -> str:
    return str(magnet.stable)

def stable_temperature(temperature_control: object) -> str:
    return str(temperature_control.stable)


class MagneticField(Parameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.sample_magnet = MagnetControl("sample_magnet", self.root_instrument.host)

    def get_raw(self) -> float:
        return self.sample_magnet.field

    def set_raw(self, value: float) -> None:
        self.sample_magnet.start((value, self.root_instrument.magnetic_field_rate()))
        while True:
            self._get_info()
            self._print_info()
            if self.stable:
                break
            time.sleep(1)

    def _get_info(self) -> None:
        self.B = self.sample_magnet.field
        self.stable = self.sample_magnet.stable
        _, self.status = self.sample_magnet.status

    def _print_info(self) -> None:
        print(f"B = {self.B:.3f} ({self.status}, stable={self.stable})")

    def sweep(self, start: float, end: float) -> None:
        ramp = self.root_instrument.magnetic_field_rate()
        self.set_raw(start)
        print(f"Starts sweep from {start} T to {end} T ramping {ramp} T/min")
        self.sample_magnet.start((end, self.root_instrument.magnetic_field_rate()))

    def current_stability_window(self) -> None:
        print(self.sample_magnet.current_stabilitywindow)

    def tesla_stability_window(self) -> None:
        print(self.sample_magnet.tesla_stabilitywindow)


class TemperatureControl(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.temperature_control = ContinuousTemperatureControl(
            "temperature_control", self.root_instrument.host
        )
        self.adr_control = ADRControl(
            "adr_control", self.root_instrument.host
        )

    def get_raw(self):
        return self.temperature_control.kelvin

    def set_raw(self, value: float) -> None:
        if value < 0.3 and self.adr_control.operation_mode == "card":
            self.adr_control.operation_mode("ard")
            print("Single shot mode is active")
        elif value >= 0.3 and self.adr_control.operation_mode == "ard":
            self.adr_control.operation_mode("card")
            print("Continuous cooling is active")
        self.temperature_control.start((value, self.root_instrument.temperature_rate()))
        print(f"Waiting for {value} K ")
        while True:
            self._get_info()
            self._print_info()
            if self._is_done():
                break
            time.sleep(1)

    def _get_info(self) -> None:
        self.ramping_info = self.temperature_control.get_ramping_info()
        self.T = self.temperature_control.kelvin

    def _print_info(self) -> None:
        print(f"T = {self.T:.3f} K")
        print(self.ramping_info)

    def _is_done(self) -> bool:
        return self.ramping_info["ramp_done"] and self.ramping_info["ready_to_ramp"]

    def sweep(self, start: float, end: float):
        ramp = self.root_instrument.temperature_rate()
        self.set_raw(start)
        print(f"Starts sweep from {start} K to {end} K ramping {ramp} K/min")
        self.sample_magnet.start((end, self.root_instrument.temperature_rate()))


def BSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    ramp: float,
    delay: float,
    write_period: float,
    *param_meas,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.magnetic_field)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.magnetic_field,))

    kiutra.magnetic_field_rate(ramp)

    with meas.run() as datasaver:
        kiutra.magnetic_field.sweep(start, end)
        stable = False
        B_2 = start
        while all((not stable, B_2 < end)):
            stable = kiutra.magnetic_field.sample_magnet.stable
            B_1 = kiutra.magnetic_field.sample_magnet.field
            params_get = [(param, param.get()) for param in params]
            B_2 = kiutra.magnetic_field.sample_magnet.field
            datasaver.add_result(
                (kiutra.magnetic_field, (B_1 + B_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset

def TSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    ramp: float,
    delay: float,
    write_period: float,
    *param_meas,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.temperature)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.temperature,))

    kiutra.temperature_ramp(ramp)

    with meas.run() as datasaver:
        kiutra.temperature.sweep(start, end)
        stable = False
        T_2 = start
        while all((not stable, T_2 < end)):
            stable = kiutra.temperature.stable
            T_1 = kiutra.temperature.get_raw()
            params_get = [(param, param.get()) for param in params]
            T_1 = kiutra.temperature.get_raw()
            datasaver.add_result(
                (kiutra.temperature, (T_1 + T_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset


# class SampleLoader(Parameter):
#     def __init__(self, name: str, **kwargs: Any) -> None:
#         super().__init__(name, **kwargs)


    # Maybe it is just easier to just set up the qdac immidiately \
    # after loading has completed in a detached piece of code
    # 
    # def load_cool_in_configuration(self, *cooling_configuration) -> None:
    #     self.load()
    #     params = []
    #     for param in cooling_configuration:
    #         if isinstance(param, ParameterBase):
    #             params.append(param)
    #             meas.register_parameter(param, setpoints=(kiutra.temperature,))