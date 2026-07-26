(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM hoist
VAR_INPUT
    RaiseCmd     : BOOL;
    LowerCmd     : BOOL;
    UpperLimitOK : BOOL;  (* NC: TRUE = clear, FALSE = upper over-travel *)
    LowerLimitOK : BOOL;  (* NC: TRUE = clear, FALSE = lower over-travel *)
    SlackRopeOK  : BOOL;  (* NC: TRUE = taut,  FALSE = slack rope *)
    EStop        : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    HoistUp   : BOOL;
    HoistDown : BOOL;
    BrakeSet  : BOOL;  (* TRUE = brake engaged *)
END_VAR

(* Asymmetric directional protection: upper limit blocks up only,
   lower limit / slack rope block down only. *)
IF NOT EStop THEN
    HoistUp := FALSE;
    HoistDown := FALSE;
ELSIF RaiseCmd AND NOT LowerCmd AND UpperLimitOK THEN
    HoistUp := TRUE;
    HoistDown := FALSE;
ELSIF LowerCmd AND NOT RaiseCmd AND LowerLimitOK AND SlackRopeOK THEN
    HoistUp := FALSE;
    HoistDown := TRUE;
ELSE
    HoistUp := FALSE;
    HoistDown := FALSE;
END_IF;

(* Brake engaged whenever not moving. *)
BrakeSet := NOT (HoistUp OR HoistDown);

END_PROGRAM
