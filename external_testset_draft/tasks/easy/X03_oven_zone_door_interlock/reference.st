(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM oven_zones
VAR_INPUT
    DoorClosed : BOOL;  (* TRUE = door closed *)
    Temp1      : INT;   (* zone-1 temperature, 0..400 *)
    Temp2      : INT;   (* zone-2 temperature, 0..400 *)
    Enable     : BOOL;
    EStop      : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Heater1 : BOOL;
    Heater2 : BOOL;
END_VAR
VAR CONSTANT
    SET1 : INT := 200;
    SET2 : INT := 250;
END_VAR

(* Shared door interlock gates both zone thermostats.
   Pure thresholds, no hysteresis. *)
IF NOT EStop OR NOT Enable OR NOT DoorClosed THEN
    Heater1 := FALSE;
    Heater2 := FALSE;
ELSE
    Heater1 := Temp1 < SET1;
    Heater2 := Temp2 < SET2;
END_IF;

END_PROGRAM
