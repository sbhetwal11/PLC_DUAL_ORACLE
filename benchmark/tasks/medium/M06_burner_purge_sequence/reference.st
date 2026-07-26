PROGRAM burner
VAR_INPUT
    StartPB : BOOL;
    StopPB  : BOOL;
    EStop   : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
    Flame   : BOOL;
END_VAR
VAR_OUTPUT
    Fan      : BOOL;
    Fuel     : BOOL;
    Ignition : BOOL;
END_VAR
VAR
    State : INT;
    T1    : TON;   (* purge timer *)
    T2    : TON;   (* ignition-trial timer *)
END_VAR

(* T#Ns = N scan ticks (1 tick = 1 s). *)
T1(IN := State = 1, PT := T#3s);
T2(IN := State = 2, PT := T#2s);

IF (NOT EStop) OR StopPB THEN
    State := 0;
ELSE
    CASE State OF
    0:
        IF StartPB THEN
            State := 1;
        END_IF;
    1:
        IF T1.Q THEN
            State := 2;
        END_IF;
    2:
        IF T2.Q THEN
            IF Flame THEN
                State := 3;
            ELSE
                State := 0;
            END_IF;
        END_IF;
    3:
        IF NOT Flame THEN
            State := 0;
        END_IF;
    END_CASE;
END_IF;

CASE State OF
0:
    Fan := FALSE; Fuel := FALSE; Ignition := FALSE;
1:
    Fan := TRUE;  Fuel := FALSE; Ignition := FALSE;
2:
    Fan := TRUE;  Fuel := TRUE;  Ignition := TRUE;
3:
    Fan := TRUE;  Fuel := TRUE;  Ignition := FALSE;
END_CASE;

END_PROGRAM
