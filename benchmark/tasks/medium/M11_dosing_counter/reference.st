PROGRAM dosing
VAR_INPUT
    Trigger : BOOL;
    Reset   : BOOL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
END_VAR
VAR
    Count       : INT;
    PrevTrigger : BOOL;
END_VAR
VAR CONSTANT
    N : INT := 3;
END_VAR

(* Reset dominates; otherwise count a rising edge of Trigger, capped at N. *)
IF Reset THEN
    Count := 0;
ELSIF Trigger AND NOT PrevTrigger AND Count < N THEN
    Count := Count + 1;
END_IF;

PrevTrigger := Trigger;
Done := Count >= N;

END_PROGRAM
