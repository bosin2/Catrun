# Branch cleanup — 2026-11-11

User requested GitHub branch cleanup before placement work. No open PRs. Default and current branch main preserved unchanged. Remote and local branch lists now contain main only. Merged branches remain in main history; ten review snapshots remain as remote archival tags.

| Removed branch | Original commit | Recovery |
|---|---|---|
| `SoundEffectVisualUpgrade` | `168c5b9b11eb232cf77a6a1bee018187e9d86d3c` | Contained in main history |
| `feature/monster-ai` | `ce8a9b6b6524ffc9ff606b97041aa9355827e0cf` | Contained in main history |
| `feature/sound-ripple-bp` | `3d5a106bdefaa323913dd06dbda82f7aa7458fef` | Contained in main history |
| `feature/sound-system` | `48b351356d1f896dd7383fd5056e15cd4b43fc42` | Contained in main history |
| `review/ultra-1-armor-ai` | `6e0f292c8e8165e5e12540e19aba4f85a461b0a2` | `archive/2026-11-11/review/ultra-1-armor-ai` |
| `review/ultra-1-armor-ai-base` | `a65eca4c7906b9070413a3a9f8b60cca25fb22c4` | `archive/2026-11-11/review/ultra-1-armor-ai-base` |
| `review/ultra-2-sound-core` | `69cbe520d9ba3f0af138828db81aa639abe0ed8d` | `archive/2026-11-11/review/ultra-2-sound-core` |
| `review/ultra-2-sound-core-base` | `a401ce9497ce0f748b3b4b2308ae96101e6a160c` | `archive/2026-11-11/review/ultra-2-sound-core-base` |
| `review/ultra-3-cat-bell-mark` | `433afd8a18324b4c555c6af1afb6e528e09c9a6e` | `archive/2026-11-11/review/ultra-3-cat-bell-mark` |
| `review/ultra-3-cat-bell-mark-base` | `2dbfd1b5c75236dfc7cb9d3562e8d3373c42d055` | `archive/2026-11-11/review/ultra-3-cat-bell-mark-base` |
| `review/ultra-4-candle-vision` | `031140aed3beca80cfc5e4af50bb30a3ec26c20f` | `archive/2026-11-11/review/ultra-4-candle-vision` |
| `review/ultra-4-candle-vision-base` | `375c033fadf5d0661edb02f901da9c1531fc6680` | `archive/2026-11-11/review/ultra-4-candle-vision-base` |
| `review/ultra-5-basket-door-path` | `3a08b334d629dbbd91f88ef929c4e9110bd8dd18` | `archive/2026-11-11/review/ultra-5-basket-door-path` |
| `review/ultra-5-basket-door-path-base` | `bfb5e081b31bc26b6ef91a97a10dae72b05c2274` | `archive/2026-11-11/review/ultra-5-basket-door-path-base` |
| `sound-wave-visuals` | `60346cf56949e643f932f5e5197f5632f9ea709c` | Contained in main history |

Restore any branch if needed: `git push origin <original-commit>:refs/heads/<branch-name>`.
Expected SHA leases and an atomic push protected against concurrent branch updates. Main remained `aa6c943e98394e90a4e39bda6a6c00ec07b03323`.
