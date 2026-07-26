(* DRAFT - pending expert PLC review. External family-level test candidate. *)
(* NOTE (reviewer): from a cold start TRest imposes a MIN_REST delay before the
   first start, because the rest timer is not pre-loaded on power-up - a modelling
   artifact, documented rather than changed. This is a start/stop anti-short-cycle
   scheme (motor cycles on/off, LoadValve tracks the motor), not a true
   continuous-run load/unload valve scheme. *)
PROGRAM air_compressor
VAR_INPUT
    Pressure : INT;   (* psi, 0..150 *)
    Enable   : BOOL;
    EStop    : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Motor     : BOOL;  (* also the running-state latch *)
    LoadValve : BOOL;
END_VAR
VAR
    Demand : BOOL;
    TRun   : TON;      (* measures elapsed run time  *)
    TRest  : TON;      (* measures elapsed rest time *)
END_VAR
VAR CONSTANT
    P_SET : INT := 100;
END_VAR

(* Single-threshold demand (no hysteresis band). *)
Demand := Pressure < P_SET;

(* Both timers called once, unconditionally, at top level.
   TRun counts while running; TRest counts while stopped. Motor here is the
   previous-scan running state (read before assignment). *)
TRun(IN := Motor, PT := T#3s);
TRest(IN := NOT Motor, PT := T#3s);

IF NOT EStop OR NOT Enable THEN
    Motor := FALSE;
ELSIF Motor THEN
    (* running: may stop only when demand gone AND minimum run met *)
    Motor := NOT ((NOT Demand) AND TRun.Q);
ELSE
    (* stopped: may start only when demand present AND minimum rest met *)
    Motor := Demand AND TRest.Q;
END_IF;

LoadValve := Motor;

END_PROGRAM
