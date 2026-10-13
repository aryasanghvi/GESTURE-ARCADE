"""Shared gesture input with smoothing, stable-pose gating and hold actions."""
import math

class GestureController:
    def __init__(self, swipe_threshold=0.12, smoothing=0.35):
        self.prev = None
        self.swipe_threshold = swipe_threshold
        self.smoothing = smoothing
        self._xy = None
        self._candidate = 'none'
        self._stable_since = None
        self._neutral_since = None
        self._armed = True
        self._fired_for_pose = False
        self._last_time = None
        self._feedback = ''
        self.swipe = None

    def update(self, frame_data, now=None):
        import time
        now = time.monotonic() if now is None else now
        self.swipe = None
        if not frame_data or not frame_data.get('present'):
            self.prev = self._xy = None
            self._candidate = 'none'; self._stable_since = None
            self._neutral_since = now; self._armed = True; self._fired_for_pose = False
            return {'present':False,'x':.5,'y':.5,'gesture':'none','swipe':None,'fire':False,'pinch':False,'action':None,'progress':0.0,'feedback':'Show your hand'}
        x,y=float(frame_data.get('x',.5)),float(frame_data.get('y',.5))
        if self._xy:
            x=self.smoothing*x+(1-self.smoothing)*self._xy[0]
            y=self.smoothing*y+(1-self.smoothing)*self._xy[1]
        if self.prev:
            dx,dy=x-self.prev[0],y-self.prev[1]
            if math.hypot(dx,dy)>=self.swipe_threshold: self.swipe=(self.prev[0],self.prev[1],x,y)
        self.prev=self._xy=(x,y)
        g=frame_data.get('gesture','none')
        if g != self._candidate:
            self._candidate=g; self._stable_since=now; self._fired_for_pose=False
        stable=now-(self._stable_since if self._stable_since is not None else now)
        if g not in ('pinch','two_finger','fist','open_palm'):
            if self._neutral_since is None:self._neutral_since=now
            if now-self._neutral_since>=.3:
                self._armed=True; self._fired_for_pose=False
        else:self._neutral_since=None
        holds={'pinch':1.0,'two_finger':1.25,'fist':0.9,'open_palm':2.0}
        action=None; progress=0.0
        if g in holds:
            progress=min(1.0,stable/holds[g])
            if stable>=holds[g] and self._armed and not self._fired_for_pose:
                action={'pinch':'select','two_finger':'restart','fist':'back','open_palm':'pause'}[g]
                self._fired_for_pose=True; self._armed=False
                self._feedback={'select':'Selected','restart':'Restart requested — repeat two fingers to confirm','back':'Going back','pause':'Pause/resume'}[action]
        else: progress=0.0
        return {'present':True,'x':x,'y':y,'gesture':g,'swipe':self.swipe,'fire':g=='open_palm','pinch':g=='pinch','action':action,'progress':progress,'feedback':self._feedback}
