"""Unequal wheel dynamics, inertia, stopping and legacy negotiation without hardware."""
import math
import struct
import sys
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from car_control import CarController, Move
from synchronized_motion import SynchronizedMove
from protocol import Status, Capabilities, STOP, ARM, SET_PARAM, GET_STATUS


def state_at(planner, distances, speeds=(0, 0)):
    counts = [round(d * sign / scale) for d, sign, scale in
              zip(distances, planner.signs, planner.mm_per_count)]
    return Status(2, 0, *counts, *speeds, 0, 0, 0)


class DynamicCar(CarController):
    def __init__(self, speed_gain=(1.0, 1.15), mode='normal'):
        self.now=0.;self.positions=[0.,0.];self.velocity=[0.,0.]
        self.command=(0,0);self.state=0;self.params={};self.history=[];self.mode=mode
        self.gain=speed_gain
        super().__init__(self,clock=lambda:self.now,sleep=self.advance,right_motor_reversed=False)
        self.synchronized_motion=True
        self.capabilities=Capabilities(1,400)

    def write(self, packet):
        self.command=struct.unpack('<ii',packet[8:16]);self.state=2
        self.history.append(self.command)

    def advance(self, dt):
        self.now+=dt
        for i in range(2):
            target=self.command[i]*self.gain[i] if self.mode!='stuck' else 0
            self.velocity[i]+=(target-self.velocity[i])*min(1,dt/0.08)
            self.positions[i]+=self.velocity[i]*dt

    def request(self, kind, payload=b''):
        if kind==STOP:
            self.command=(0,0);self.state=0
        elif kind==ARM:
            self.state=1
        elif kind==SET_PARAM:
            key,value=struct.unpack('<BI',payload);self.params[key]=value
        counts=[round(x*c/(math.pi*66.3)) for x,c in zip(self.positions,(1469,1471))]
        faults=4 if self.mode=='fault' and self.history else 0
        if self.mode=='disconnect' and self.history:
            raise RuntimeError('lost telemetry')
        return Status(3 if faults else self.state,faults,*counts,*map(round,self.velocity),0,0,0)


class SynchronizedTests(unittest.TestCase):
    def test_leading_wheel_is_slowed_for_both_turn_and_straight(self):
        for action in ('forward','backward','left','right'):
            planner=SynchronizedMove(Move(action,180 if action in ('left','right') else 50).targets(),(0,0),200)
            command=planner.step(state_at(planner,(35,30)),0)
            self.assertLess(abs(command[0]),abs(command[1]))
            self.assertEqual(tuple(1 if v>0 else -1 for v in command),planner.signs)
            command=planner.step(state_at(planner,(45,30)),.04)
            self.assertGreater(abs(command[0]),0)
            self.assertLess(abs(command[0]),abs(command[1]))
            self.assertNotEqual(command[1],0)

    def test_ground_log_large_lead_does_not_clear_one_wheel_target(self):
        # Second user run was ON THE FLOOR. Old hard gap gate alternately
        # cleared right and left targets long before the 20cm endpoint.
        planner=SynchronizedMove(Move('forward',20).targets(),(1387,1378),200)
        samples=[(1575,1628,141,155),(1627,1674,169,140),
                 (1898,1780,197,70),(2038,1853,127,84),
                 (2145,1977,70,112),(2295,2408,70,169)]
        previous=0
        for i,(lc,rc,ls,rs) in enumerate(samples):
            command=planner.step(Status(2,0,lc,rc,ls,rs,0,0,40),i*.04)
            self.assertTrue(all(40<=v<=200 for v in command),command)
            self.assertLessEqual(abs(planner.correction-previous),3.200001)
            previous=planner.correction

    def test_correction_is_bounded_smooth_and_sign_symmetric(self):
        for action in ('forward','backward','left','right'):
            planner=SynchronizedMove(Move(action,180 if action in ('left','right') else 50).targets(),(0,0),200)
            for i in range(20):
                ds=(90,60) if i<10 else (60,90)
                vs=tuple(s*v for s,v in zip(planner.signs,(180,120)))
                before=planner.correction
                command=planner.step(state_at(planner,ds,vs),i*.04)
                self.assertTrue(all(160<=abs(v)<=200 for v in command))
                self.assertLessEqual(abs(planner.correction-before),3.200001)
                self.assertEqual(tuple(1 if v>0 else -1 for v in command),planner.signs)

    def test_common_deceleration_before_arrival(self):
        planner=SynchronizedMove(Move('forward',50).targets(),(0,0),400)
        fast=planner.step(state_at(planner,(100,100)),0)
        slow=planner.step(state_at(planner,(475,475)),.04)
        self.assertLess(max(map(abs,slow)),max(map(abs,fast)))

    def test_arrival_while_moving_waits_for_stability(self):
        planner=SynchronizedMove(Move('forward',10).targets(),(0,0),200)
        status=state_at(planner,planner.lengths,(150,150))
        self.assertEqual(planner.step(status,0),(0,0))
        self.assertEqual(planner.step(status,.2),(0,0))
        stopped=state_at(planner,planner.lengths)
        self.assertEqual(planner.step(stopped,.24),(0,0))
        self.assertEqual(planner.step(stopped,.32),(0,0))
        self.assertIsNone(planner.step(stopped,.44))

    def test_coast_overshoot_reports_error_and_never_reverses(self):
        planner=SynchronizedMove(Move('forward',10).targets(),(0,0),200)
        self.assertEqual(planner.step(state_at(planner,(99,99),(100,100)),0),(0,0))
        stopped=state_at(planner,(120,120))
        planner.step(stopped,.04);planner.step(stopped,.08)
        with self.assertRaisesRegex(RuntimeError,'误差'):
            planner.step(stopped,.25)

    def test_real_20cm_log_stops_short_without_low_speed_restart(self):
        # Start right=-1; at rest left=1386/right=1375. Residual=3.5/5.1 mm.
        planner=SynchronizedMove(Move('forward',20).targets(),(0,-1),200)
        coast=Status(2,0,1263,1263,155,155,0,0,40)
        self.assertEqual(planner.step(coast,0),(0,0))
        stopped=Status(2,0,1386,1375,0,0,0,0,40)
        for now in (.04,.08,.12,.16,.20):
            self.assertEqual(planner.step(stopped,now),(0,0))
        with self.assertRaisesRegex(RuntimeError,'未自动补进'):
            planner.step(stopped,.28)
        self.assertAlmostEqual(planner.errors_mm[0],3.5447,places=3)
        self.assertAlmostEqual(planner.errors_mm[1],5.0975,places=3)

    def test_all_short_stops_report_residual_without_restarting(self):
        for remaining in (5.2,10,30):
            planner=SynchronizedMove(Move('forward',20).targets(),(0,0),200)
            # Moving sample enters the common coast phase before final stop.
            self.assertEqual(planner.step(state_at(planner,(175,175),(200,200)),0),(0,0))
            stopped=state_at(planner,tuple(n-remaining for n in planner.lengths))
            planner.step(stopped,.04);planner.step(stopped,.08)
            with self.assertRaisesRegex(RuntimeError,'未自动补进'):
                planner.step(stopped,.25)

    def test_asymmetric_dynamics_four_directions_settle_within_tolerance(self):
        # This plant has an 80ms first-order coast response. Give it its own
        # calibrated stopping model, rather than relying on automatic restarts
        # to hide a mismatch between plant and initial real-car tuning values.
        for action in ('forward','backward','left','right'):
            car=DynamicCar()
            move=Move(action,90 if action in ('left','right') else 20,200)
            with patch.object(SynchronizedMove,'COAST_DECEL_MM_S2',2500):
                self.assertTrue(car.move(move),action)
            goal=[n*math.pi*66.3/c for n,c in zip(move.targets(),(1469,1471))]
            self.assertTrue(all(abs(p-g)<=5.1 for p,g in zip(car.positions,goal)),(action,car.positions,goal))
            self.assertLess(max(map(abs,car.velocity)),20)
            self.assertEqual(car.params[9],0)
            self.assertEqual(car.state,0)
            self.assertEqual(car.history[-1],(0,0))

    def test_uncalibrated_coast_model_reports_short_stop_and_cleans_up(self):
        car=DynamicCar()
        with patch.object(SynchronizedMove,'LATENCY_S',0.15), self.assertRaisesRegex(RuntimeError,'未自动补进'):
            car.move(Move('forward',20,200))
        self.assertEqual(car.state,0)
        self.assertEqual(car.params[9],0)
        self.assertLess(max(map(abs,car.velocity)),20)
        first_zero=car.history.index((0,0))
        self.assertTrue(all(pair==(0,0) for pair in car.history[first_zero:]))

    def test_fault_disconnect_cancel_and_timeout_cleanup(self):
        for mode in ('fault','disconnect','stuck'):
            car=DynamicCar(mode=mode)
            with self.assertRaises(RuntimeError):
                car.move(Move('forward',10,200))
            self.assertEqual(car.params[9],0)
            self.assertEqual(car.command,(0,0))
        car=DynamicCar();cancel=threading.Event()
        def sleep(dt):
            car.advance(dt);cancel.set()
        car.sleep=sleep
        self.assertFalse(car.move(Move('forward',10),cancel))
        self.assertEqual(car.params[9],0)

    def test_motion_capability_disables_reverse_without_enabling_vision(self):
        car=CarController(object())
        with patch('car_control.send_and_read',return_value=[(0xc0,1,b'EVM1'+struct.pack('<HH',1,400))]):
            cap=car.detect_capabilities()
        self.assertTrue(cap.bridge_fixed)
        self.assertFalse(cap.has_vision)
        self.assertFalse(car.right_motor_reversed)
        self.assertTrue(car.synchronized_motion)
        with self.assertRaisesRegex(RuntimeError,'不支持'):
            car.sensing()


if __name__=='__main__':
    unittest.main()
