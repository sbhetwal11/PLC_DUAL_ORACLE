PROGRAM two_hand
VAR_INPUT
    LH : BOOL;
    RH : BOOL;
END_VAR
VAR_OUTPUT
    Actuator : BOOL;
END_VAR
VAR
    Armed : BOOL;
END_VAR

(* Arm only when both buttons are released; lose arming if exactly one is held. *)
IF NOT LH AND NOT RH THEN
    Armed := TRUE;
ELSIF (LH AND NOT RH) OR (RH AND NOT LH) THEN
    Armed := FALSE;
END_IF;

Actuator := LH AND RH AND Armed;

END_PROGRAM
