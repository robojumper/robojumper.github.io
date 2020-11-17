---
title: "Load Order"
summary: "This article investigate what kinds of load orders there are in XCOM 2 and how to work with them..."
date: 2020-11-17T17:45:00+01:00
tags: ["unrealscript", "xcom2"]
---

"How do I fix my load order?" ask many many XCOM 2 mod users, but there are several kinds of load orders, some of which are unreliable and can't
even be changed. We're going to look at the different kinds of load orders, clear up some misconceptions, and see how they affect mod dependencies.

## Config files

This is the most important and most impactful kind of load order. As a quick reminder, config files consist of key-value
pairs (KVP) that are conceptually inserted into a multi-map (a key-values map where multiple values can correspond to one key).

We have access to some syntax translating to commands for the config map:

* `Key=Value`: Set the entry `Key` to `Value`
* `+Key=Value`: Add to entry `Key` the value `Value` if not present
* `.Key=Value`: Add to entry `Key` the value `Value`
* `-Key=Value`: Remove from entry `Key` the value `Value` if present
* `!Key=()`: Clear entry `Key`

This is a strictly serial process. Config files and the lines within are processed in order.

{{< interjection kind="info" >}}
For base-game config files and files in the user directory (`Documents/My Games/XCOM 2 (WotC)/XComGame/Config`), `Key=Value`
entries are interpreted as `+Key=Value`.<p />
{{< /interjection >}}

Only after all config files have been loaded, `config` variables are imbued with the values from the config map.
How it precisely works depends on the kind of variable.

* Primitive types use the value inserted last
* Static (fixed-size) arrays look for `VarName[0]`, `VarName[1]`, ... keys and use the respective value inserted last
* Arrays are special

### Array indexing

`+VarName=...` and `VarName[_]=...` have no interaction at all. Several `+VarName=...` KVPs produce a key with multiple values,
`VarName[_]=...` KVPs with different indices produce different keys.

Arrays look for the `VarName` key and insert all entries in order into the array. Only if `VarName` isn't found,
they look for `VarName[0]`, `VarName[1]`, ... keys, using the last inserted value, until one isn't found.

```ini
+CArray="PlusZero"
+CArray="PlusOne"
CArray[1]="AtOne"
; results in CArray = ["PlusZero", "PlusOne"] in UnrealScript
```

```ini
CArray[0]="AtZero"
CArray[1]="AtOne"
CArray[3]="AtThree"
; results in CArray = ["AtZero", "AtOne"] in UnrealScript
```

### Textual identity

It's also a strictly textual process -- the config parser has no knowledge of the actual types of the variables:

```ini
+IArray=1
+IArray=01
+IArray=1
; results in IArray = [1, 1] in UnrealScript
```

```ini
+SArray=(i=5)
+SArray=(i=6)
-SArray=(i=5)
-SArray=(i = 6)
; results in SArray = [A { i = 6 }] in UnrealScript
```

{{< interjection kind="advice" >}}
Minor formatting differences such as white-space, indentation, capitalization and leading zeros are relevant for the removal of entries.<p />
{{< /interjection >}}

### Load order

Since single-value types use the last inserted entry, the config file processed last usually wins.
But at the same time, if a certain approach relies on removing previous array entries, only the first
processed mod has any chance to textually match an original entry. Config load order is important, and here's the
guaranteed parts of the order:

1. User directory (`Documents/My Games/XCOM 2 (WotC)/XComGame/Config`)
2. DLC directories (`XCOM 2/XCom2-WarOfTheChosen/XComGame/DLC/*/Config`)
3. Mod directories (`XCOM 2/XCom2-WarOfTheChosen/XComGame/Mods/*/Config` and `workshop/content/268500/*/Config`)

It is obvious that base-game config is loaded first. DLCs happen to be loaded after that, and then it's mod directories.
The game knows of the mod directories through a config array `ModRootDirs` in `XComEngine.ini`, and it turns out that the
order there determines whether workshop mods or local mods are loaded first! Within these orders, there are different rules:

* Workshop directories load order is unclear and believed to be either based on workshop ID or subscription date
* Mod directories are loaded alphabetically[^alpha]

{{< interjection kind="advice" >}}
A common misconception is that the order of the `ActiveMods` in `XComModOptions.ini` determines config load order. For the
longest time, the Alternative Mod Launcher had offered a "load order" column that affected only the `ActiveMods` array.

This is wrong. Config load order is rarely guaranteed and should not be relied on by mod authors.
{{< /interjection >}}

### Workarounds

This causes a bunch of issues in practice. Some base-game config arrays use `VarName[_]=...` syntax, so mods cannot use the
`+VarName` syntax to add to the array -- and explicit indices would be incompatible with other mods. One example of this are
ability availability codes -- a `config` and a `localized` array that map a tactical condition error code to a user-displayed string.

It can be useful to modify these arrays from code: Declare copies of the arrays in your own class, fill them in from your private config
files, then copy them over at runtime (code simplified from [Rising Tides: The Program](https://steamcommunity.com/sharedfiles/filedetails/?id=1500499606)):

```java
var config array<name> NewAbilityAvailabilityCodes;
var localized array<String> NewAbilityAvailabilityStrings;

static event OnPostTemplatesCreated()
{
	local X2AbilityTemplateManager	AbilityTemplateManager;
	local int						idx;

	AbilityTemplateManager = X2AbilityTemplateManager(class'Engine'.static.FindClassDefaultObject("XComGame.X2AbilityTemplateManager"));

	// If there are more codes than strings, this inserts blank strings to bring them to equal before adding our new codes
	// If there are more strings than codes, this cuts off the excess before adding our new codes
	AbilityTemplateManager.AbilityAvailabilityStrings.Length = AbilityTemplateManager.AbilityAvailabilityCodes.Length;

	// Append new codes and strings to the arrays
	for (idx = 0; idx < default.NewAbilityAvailabilityCodes.Length; idx++)
	{
		AbilityTemplateManager.AbilityAvailabilityCodes.AddItem(default.NewAbilityAvailabilityCodes[idx]);
		AbilityTemplateManager.AbilityAvailabilityStrings.AddItem(default.NewAbilityAvailabilityStrings[idx]);
	}
}
```

This avoids compatibility issues and even fixes errors arising from mods doing the config entries wrong. I do something similar
for [WotC: More Photobooth Options](https://steamcommunity.com/sharedfiles/filedetails/?id=1139981009), and custom code can help
the many cases where mod compatibility is a concern but the config syntax is not expressive enough (perhaps even
[custom Rulers](https://github.com/X2CommunityCore/X2WOTCCommunityHighlander/pull/454)).

When the code becomes too complex, the Highlander sometimes provides features for mod code to easily modify config tables
in a compatible way. For example, the Highlander has a ["Loot Table API"](https://x2communitycore.github.io/X2WOTCCommunityHighlander/tactical/LootTableAPI/)
that allows mods to modify the enemy tactical loot drops without stomping on other mods' changes.

## Script packages

This config load order produces another load order because config files are the way mods tell the game to load script packages.
Every mod with a script package has at least one entry in its `NonNativePackages`:

```ini
[Engine.ScriptPackages]
+NonNativePackages=LW_Tuple
+NonNativePackages=DetailedSoldierListWOTC
```

Not only affects this which packages are loaded, but also the order in which they are loaded.

### Dependencies

Package B depends on package A if A needs to be compiled and loaded before package B.
Contrary to content packages, script packages do not cause their dependencies to be loaded automatically. We can visualize, as an example, the
dependency graph for Long War of the Chosen @ [dfbe52c](https://github.com/long-war-2/lwotc/tree/dfbe52c0428ea639bcb54c09c1d79e042c34b32d) because
it probably has the most complex dependency graph:

![dependency graph lwotc](/img/load-order/lw2.png)

This dependency graph is a [directed acyclic graph](https://en.wikipedia.org/wiki/Directed_acyclic_graph) (DAG): The edges are *directed*
(an edge from A to B means B depends on A, but not the other way around) and the nodes are *acyclic* (there aren't any cycles).

Cycles are impossible because script packages are compiled and loaded one after another, but now we need to find out a good order for
our packages to be compiled and loaded in.

* If the packages are listed in the wrong order for the compiler, the compiler will throw errors.
* If the packages are loaded in the wrong order at run-time,
the game will have incredible bugs arising from certain classes and functions missing from the loaded UnrealScript bytecode.

The requirement for our `NonNativePackages` order is that if there is an edge from `A -> B`, then A must come before B in the order. Such an order
is called a [topological ordering](https://en.wikipedia.org/wiki/Topological_sorting), always exists for a DAG, and one such ordering can be found
-- unsurprisingly -- in LWotC's `XComEngine.ini`

```ini
[Engine.ScriptPackages]
+NonNativePackages=LW_Tuple
+NonNativePackages=XModBase_Interfaces
+NonNativePackages=XModBase_Core_2_0_2
+NonNativePackages=LW_XModBase
+NonNativePackages=WallClimbOverride
+NonNativePackages=LWUtilities
+NonNativePackages=ModConfigMenuAPI
+NonNativePackages=LW_XCGS_ModOptions
+NonNativePackages=LW_XCGS_ToolboxOptions
+NonNativePackages=LW_SMGPack_Integrated
+NonNativePackages=LW_LaserPack_Integrated
+NonNativePackages=NewPromotionScreenByDefault_Integrated
+NonNativePackages=PI_Integrated
+NonNativePackages=LW_PerkPack_Integrated
+NonNativePackages=LW_OfficerPack_Integrated
+NonNativePackages=LW_AlienPack_Integrated
+NonNativePackages=LW_Toolbox_Integrated
+NonNativePackages=LW_WeaponsAndArmor
+NonNativePackages=LW_FactionBalance
+NonNativePackages=LW_Overhaul
```

### Meta-mods

We call mods that modify other mods "meta-mods", and in this example, we're looking to make a mod that requires some code from `LW_WeaponsAndArmor`.
It's tempting to make our `NonNativePackages` look like this:

```ini
[Engine.ScriptPackages]
+NonNativePackages=LW_WeaponsAndArmor
+NonNativePackages=MyMetaMod
```

Unfortunately, this has a fatal problem: Config load order is not guaranteed. If our meta-mod configs are loaded before LWotC's,
then `LW_WeaponsAndArmor` is loaded before all of its dependencies. The dependency graph looks like this:

![transitive dependency graph meta-mod](/img/load-order/metamod.png)

The pink highlighted packages are *transitive dependencies* of `MyMetaMod`: `MyMetaMod`'s direct dependencies, and dependencies of its dependencies and so on.
All transitive dependencies need to be listed in `NonNativePackages` to defend against bad load order:

```ini
[Engine.ScriptPackages]
+NonNativePackages=LW_Tuple
+NonNativePackages=XModBase_Interfaces
+NonNativePackages=XModBase_Core_2_0_2
+NonNativePackages=LW_XModBase
+NonNativePackages=LWUtilities
+NonNativePackages=LW_XCGS_ModOptions
+NonNativePackages=LW_SMGPack_Integrated
+NonNativePackages=LW_PerkPack_Integrated
+NonNativePackages=LW_WeaponsAndArmor
+NonNativePackages=MyMetaMod
```

This is the minimal packages list -- we could also just wholesale copy the entire LWotC `NonNativePackages` list.

{{< interjection kind="advice" >}}
If LWotC receives an update that changes the order in its package list, `MyMetaMod` needs to be updated too -- otherwise the outdated
`MyMetaMod` can potentially mess up the package load order of LWotC.<p />
{{< /interjection >}}

### Run order

Package load order is crucial for mods to even work in the first place, but it also controls the order in which DLC hooks
like `OnPostTemplatesCreated` and entry points like `CreateTemplates` are called. It can be useful for mods to do their
template modifications in a specific order, for example RPG Overhaul needs to run before Primary Secondaries for those mods to pick
up changes made to secondary weapons before creating primary versions.

The Highlander implements a system it calls
[Run order](https://github.com/X2CommunityCore/X2WOTCCommunityHighlander/issues/511) that allows mods to specify that their DLC hooks
are ran before or after other mods.[^docs] The Highlander sorts the DLCInfo classes at startup so that all DLC hooks are automatically affected:

```ini
[XCOM2RPGOverhaul CHDLCRunOrder]
RunPriorityGroup=RUN_LAST
+RunBefore="PrimarySecondaries"
+RunBefore="WOTC_LW2SecondaryWeapons"
```

## Closing words

I hope this cleared some things up. If there's one takeaway here, it's that config load order is not guaranteed and config syntax
is not expressive enough to solve many problems -- and UnrealScript code can help. For some particular problems, the Highlander can
jump in and provide additional helpers -- don't hesitate to ask if the Highlander can help with one of them.

[^alpha]: According to [Raymond Chen](https://devblogs.microsoft.com/oldnewthing/20140304-00/?p=1603), on NTFS at least it's
"B-tree order, which if you cover one eye and promise not to focus too closely looks approximately alphabetical for US-English".
[^docs]: This feature doesn't have great documentation right now. I will add a link here once the Highlander has it documented.
