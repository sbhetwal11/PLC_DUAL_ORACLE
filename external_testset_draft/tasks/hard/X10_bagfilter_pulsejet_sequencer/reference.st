(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM bag_filter
VAR_INPUT
    DP          : INT;   (* differential pressure, Pa, 0..500 *)
    ManualClean : BOOL;
    EStop       : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Valve1 : BOOL;
    Valve2 : BOOL;
    Valve3 : BOOL;
END_VAR
VAR
    State : INT;
    T1    : TON;   (* pulse-width timer *)
    T2    : TON;   (* dwell timer       *)
END_VAR
VAR CONSTANT
    DP_HIGH : INT := 300;
END_VAR

(* Both timers called once, unconditionally, at top level.
   T1 runs during any pulse state; T2 runs during any dwell state. *)
T1(IN := (State = 1) OR (State = 3) OR (State = 5), PT := T#2s);
T2(IN := (State = 2) OR (State = 4) OR (State = 6), PT := T#2s);

IF NOT EStop THEN
    State := 0;
ELSE
    CASE State OF
    0:
        IF (DP >= DP_HIGH) OR ManualClean THEN State := 1; END_IF;
    1:
        IF T1.Q THEN State := 2; END_IF;
    2:
        IF T2.Q THEN State := 3; END_IF;
    3:
        IF T1.Q THEN State := 4; END_IF;
    4:
        IF T2.Q THEN State := 5; END_IF;
    5:
        IF T1.Q THEN State := 6; END_IF;
    6:
        IF T2.Q THEN State := 0; END_IF;
    END_CASE;
END_IF;

(* One-hot pulse outputs, keyed on the current state. *)
Valve1 := EStop AND (State = 1);
Valve2 := EStop AND (State = 3);
Valve3 := EStop AND (State = 5);

END_PROGRAM
