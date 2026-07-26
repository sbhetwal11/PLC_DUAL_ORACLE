PROGRAM tank_level
VAR_INPUT
    Level : INT; (* 0..100 percent *)
END_VAR
VAR_OUTPUT
    PumpIn   : BOOL;
    ValveOut : BOOL;
END_VAR
VAR CONSTANT
    HIGH : INT := 90;
    LOW  : INT := 10;
END_VAR

(* Inlet pump: hysteresis. Off at/above HIGH, on at/below LOW, hold between. *)
IF Level >= HIGH THEN
    PumpIn := FALSE;
ELSIF Level <= LOW THEN
    PumpIn := TRUE;
END_IF;

(* Outlet valve: open at/above HIGH to prevent overflow, else closed. *)
IF Level >= HIGH THEN
    ValveOut := TRUE;
ELSE
    ValveOut := FALSE;
END_IF;

END_PROGRAM
