# CoreSLAM / BreezySLAM

Upstream: simondlevy/BreezySLAM, commit 1170285cd42a88300eddd275fc3df36e642e3a2e.
Copyright Simon D. Levy; LGPL-3.0-or-later. Original source notices are retained.
LICENSE.md contains LGPLv3, GPL-3.0.txt its incorporated GPLv3 terms.

This directory contains unmodified upstream C sources. The separate adapter is
in ../../native/slam_bridge.c. Run ../../scripts/setup_mapping.py to rebuild the
replaceable DLL in ../../.local/mapping. All application and adapter source is
provided; users may modify/relink/replace the interface-compatible library.
No restriction on reverse engineering for debugging such modifications is imposed.

The engine provides local scan matching and occupancy mapping, without global
loop closure or navigation. The application must not turn missing returns into
fabricated free space and must stop integrating invalid or unsynchronised input.
