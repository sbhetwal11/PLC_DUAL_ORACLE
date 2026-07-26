(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM paint_booth
VAR_INPUT
    SprayRequest  : BOOL;
    FanCmd        : BOOL;
    AirflowProven : BOOL;  (* diff-pressure switch: TRUE = airflow proven *)
    EStop         : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    ExhaustFan  : BOOL;
    SprayEnable : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR

(* Exhaust fan runs on command while healthy. *)
ExhaustFan := FanCmd AND EStop;

(* Purge dwell: counts only while the fan runs with airflow proven.
   Called once, unconditionally, after ExhaustFan is computed. *)
T1(IN := ExhaustFan AND AirflowProven, PT := T#4s);

(* Spray enable is a continuous permissive: revoked the instant any
   condition drops. *)
IF NOT EStop THEN
    SprayEnable := FALSE;
ELSIF SprayRequest AND ExhaustFan AND AirflowProven AND T1.Q THEN
    SprayEnable := TRUE;
ELSE
    SprayEnable := FALSE;
END_IF;

END_PROGRAM
