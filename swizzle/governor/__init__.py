"""Attacks on a governor: SWIZZLE judges what a governor did, never what it should do next.

Warden decides and applies changes. SWIZZLE's one job here is the same as with
Ghost: build states where the target is likely to err, run it, and report
independently whether it did. It issues no verdict about whether a change is
accepted; that is somebody else's seat.
"""
