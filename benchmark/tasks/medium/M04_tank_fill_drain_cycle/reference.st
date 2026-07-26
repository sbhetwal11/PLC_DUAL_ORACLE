PROGRAM tank_cycle
VAR_INPUT
    Level      : INT;  (* 0..100 percent *)
    StartCycle : BOOL;
    EStop      : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Pump  : BOOL;
    Valve : BOOL;
END_VAR
VAR
    State : INT;
END_VAR
VAR CONSTANT
    HIGH : INT := 90;
    LOW  : INT := 10;
END_VAR

(* Transitions; emergency stop forces Idle. *)
IF NOT EStop THEN
    State := 0;
ELSE
    CASE State OF
    0:
        IF StartCycle AND Level < HIGH THEN
            State := 1;
        END_IF;
    1:
        IF Level >= HIGH THEN
            State := 2;
        END_IF;
    2:
        IF Level <= LOW THEN
            State := 0;
        END_IF;
    END_CASE;
END_IF;

(* Outputs from the (updated) state *)
CASE State OF
0:
    Pump := FALSE; Valve := FALSE;
1:
    Pump := TRUE;  Valve := FALSE;
2:
    Pump := FALSE; Valve := TRUE;
END_CASE;

END_PROGRAM
