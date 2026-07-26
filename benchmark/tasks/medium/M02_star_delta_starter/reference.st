PROGRAM star_delta
VAR_INPUT
    StartPB : BOOL;
    StopPB  : BOOL;
    EStop   : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    MainK  : BOOL;
    StarK  : BOOL;
    DeltaK : BOOL;
END_VAR
VAR
    State : INT;
    T1    : TON;
END_VAR

(* Timer runs only while in the Star state (gated IN, called at top level).
   T#3s = 3 scan ticks. *)
T1(IN := State = 1, PT := T#3s);

(* State transitions *)
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
    END_CASE;
END_IF;

(* Outputs derived from the (updated) state *)
CASE State OF
0:
    MainK := FALSE; StarK := FALSE; DeltaK := FALSE;
1:
    MainK := TRUE;  StarK := TRUE;  DeltaK := FALSE;
2:
    MainK := TRUE;  StarK := FALSE; DeltaK := TRUE;
END_CASE;

END_PROGRAM
