# Loopy, in plain English

No code here — just how the thing actually works, for anyone trying to
understand or trust it.

## The idea

Imagine a small software team that never sleeps. A manager keeps a to-do board.
Three coders pull tasks off it. A reviewer checks their work. A tester runs the
tests. A security person tries to break things. A stand-in "user" actually tries
to use the product and complains loudly. And a butler stands between the whole
team and you, the human, translating what you want into what the team does.

Loopy is that team, except every member is an AI agent running in its own
terminal pane, and they coordinate by passing notes on a shared desk instead of
talking.

## The shared desk

Everything the team knows lives in one folder, `.loopy/`, like a shared desk
everyone can see:

- a **to-do board** (the `#TODO` file and the task cards behind it),
- an **inbox** for each member (a tray where others drop notes),
- a **status card** per member ("what am I doing right now"),
- a **memory notebook** per member (what they've learned, decisions they made),
- an **out-tray** where a member's helpers leave finished work.

Because it's all just files, you can look at any of it yourself, and if a member
walks out (crashes), a replacement reads their desk and picks up where they left
off. Nothing important lives only in someone's head.

## The rhythm

Every few minutes each member does the same short routine:

1. Update their status card.
2. Re-read the house rules (they're short, and they can change).
3. Check whether their notebook is stale and refresh it if so.
4. Read their inbox.
5. Collect anything their helpers finished.
6. Look at the board and grab a piece of work they're allowed to do.
7. Check whether the house is busy; if there's room, hand the heavy lifting to a
   helper.
8. Do their particular job.
9. Update their status card again — honestly.

The golden rule: this routine must finish in under a minute. Anything slow — a
build, a big test run, writing a whole feature — gets handed to a **helper**
(a background subagent) who can take as long as needed and leaves the result in
the out-tray. This is why the team always looks alive and responsive even while
real work grinds away in the background.

## The doorbell

Notes in an inbox get read on the next routine, up to a few minutes later. When
something's urgent, the sender rings a **doorbell** so the recipient does their
routine immediately. If the doorbell is broken, nothing is lost — the note still
gets read on the normal schedule. The doorbell only ever makes things faster,
never more correct.

## Why it doesn't fall over

- **Grabbing work is safe.** Two coders can reach for the same task at the same
  instant; exactly one gets it, the other is told "taken" and moves on. No
  arguments, no duplicated effort.
- **Crashes heal.** If a member goes quiet too long, a watchdog brings them
  back, and the manager hands their abandoned tasks to someone else.
- **The house can't catch fire.** Before anyone spawns a helper, they check a
  gauge: too many helpers already running, or the machine under load, and the
  answer is "wait." So the team can't accidentally spawn a hundred processes and
  crash the computer.

## Why you can trust it

- **No green lies.** A coder only says "done" when the tests pass. Then a
  reviewer and a tester independently check, and reopen it if it's not actually
  done. Saying something works when it doesn't is the one unforgivable sin.
- **Suspicious of words.** Any text that arrives from outside — a note, a task
  description, something read off the web — is treated as *information*, never as
  orders. If a note says "ignore your rules," that's recognised as an attack, set
  aside in quarantine, and reported. The mail room scrubs sneaky tricks
  (invisible characters, look-alike letters) before anything reaches a member.
- **The rules can't be quietly rewritten.** A fingerprint of the rulebook is
  taken at startup and checked every round. If someone changes the rules behind
  the team's back, the manager notices and stops.

## Talking to the team

You talk to the **butler** (alfred). You say what you want; the butler tells the
manager; the manager makes tasks; the coders build; the reviewer, tester,
security and user keep them honest. You can check in any time with a status
dashboard, or read any inbox or task card directly. When you've had enough, one
command stops everyone — and all the work-in-progress is right there on the
shared desk, waiting for next time.

That's Loopy.
