---
title: "Function Dispatch"
summary: "In which we investigate the different ways functions are called and what it means for performance..."
date: 2020-12-08T17:00:00+01:00
tags: [unrealscript]
---

Last blog post was about [Properties](../properties/), so a logical continuation is looking at
functions next. In particular, we're going to address how functions are *called* and what happens before
the function body is executed.

We're first going to look at what the generic sequence of events for a function call looks like, and then
investigate every step in more detail. The general sequence of events will go something like:

1. Find function
2. Allocate stack frame (see [Functions](../properties/#functions) in last week's blog post)
3. Default-initialize locals, copy non-`out` function arguments to stack frame, link `out` arguments
4. Execute function body

## Finding the function

UnrealScript, by default, allows subclasses to override functions. That means that in advance, we don't know which
particular function will be called when we have an object -- it's entirely possible we're looking at a subclass
and the function we're looking to call might be overridden. Last week's blog post revealed that there is a
`FindFunctionChecked` C++ function to find a function by name -- let's imagine what it might look like:

```cpp
UFunction* UObject::FindFunctionChecked(FName FuncName) {
	UFunction *Result = NULL;
	UClass *CheckClass = GetClass();
	while (CheckClass != NULL) {
		Result = CheckClass->Functions.Find(FuncName);
		if (Result != NULL) {
			return Result;
		}
		CheckClass = CheckClass->GetSuperClass();
	}
	appErrorf("Failed to find function %s in %s", FuncName.ToString(), this->ToString());
}
```

Whenever we call a function, we have to look up this function in the current class. If not found, we have to check the superclass,
and repeat until we found it.

{{< interjection kind="info" >}}
Of course, it's possible the function doesn't exist -- for example when it's a Highlander-provided function but the Highlander
is not enabled:

```text
Critical: appError called: Assertion failed: appErrorf [File:G:\BuildAgent\work\9a884cb2af69f6ff\main\XCOM2\Development\Src\Core\Src\UnObj.cpp] [Line: 2456]
Failed to find function SubscribeToOnInput in UIScreenStack XPACK_Shell_Intro.TheWorld:PersistentLevel.XComShellPresentationLayer_0.UIScreenStack_0
```
{{< /interjection >}}

This *virtual dispatch* (named after C++'s `virtual` functions) has a cost: We have to perform at least one hash map lookup every time we want
to call a function -- and more lookups the further our subclass is away from the lowest function definition. This is particularly expensive
for functions in `Object.uc` since it's the root of the inheritance chain and functions there are the furthest away they could possibly be.

### Final functions

There is one trick to mitigate this cost: The `final` keyword, which prohibits subclasses from overriding the function. The compiler
exploits this by generating a non-virtual function call -- it embeds the function reference directly as an object and lets the dynamic linker
resolve this call once, at package load time. We can measure this effect (i5-3470 @ 3.20GHz):

```java
exec function BenchFunctionCall(optional int num = 100000000)
{
	local int i;

	`log("Bench No-Op Start");
    for (i = 0; i < num; i++) { }
	`log("Bench No-Op End");

	`log("Bench Func Start");
    for (i = 0; i < num; i++) { SubFunction(); }
	`log("Bench Func End");

	`log("Bench Final Func Start");
    for (i = 0; i < num; i++) { SubFunction2(); }
	`log("Bench Final Func End");
}

function SubFunction() { }

final function SubFunction2() { }
```

* Virtual dispatch: 30ns / call
* Non-virtual dispatch: 20.2ns / call

A `private` function is always `final`. Since `private` functions are entirely invisible to outside classes and subclasses,
they also don't need virtual dispatch.

{{< interjection kind="advice" >}}
Marking functions `final` reduces the overhead from calling functions. The benefit increases the more likely it is
for instances to be further down the inheritance chain.

Basically all functions in `Object.uc` are `final`.
{{< /interjection >}}

### Delegates

Delegates always link to a concrete function and object, so there's no name lookup involved when calling through a delegate.
Still, it's more expensive than calling a final function directly because we need to retrieve the delegate property data first,
which requires more pointer accesses.

## The Stack Frame

Once we find our function, we need to allocate space for the stack frame (unless we're calling a native function, where the C++
compiler generated *whatever* code). We can try to purposefully blow up the stack frame size:

```java
final function SubFunctionSmall() {
	local int Prop1;
}

final function SubFunctionMedium() {
	local int Prop1, Prop2, Prop3, Prop4, Prop5, Prop6, Prop7, Prop8;
}

final function SubFunctionLarge() {
	local int Prop1, Prop2, Prop3, Prop4, Prop5, Prop6, Prop7, Prop8, Prop9, Prop10;
	local int Prop11, Prop12, Prop13, Prop14, Prop15, Prop16, Prop17, Prop18, Prop19, Prop20;
	local int Prop21, Prop22, Prop23, Prop24, Prop25, Prop26, Prop27, Prop28, Prop29, Prop30;
	local int Prop31, Prop32;
}
```

{{< interjection kind="info" >}}
Nevermind my "unreferenced local variable" warnings.<p />
{{< /interjection >}}

With a baseline of no locals, the overhead of locals can be determined:

* Baseline (no locals): 20.8ns / call
* Small (1 int local): 57.0ns / call
* Medium (8 int locals): 58.9ns / call
* Large (8 int locals): 62.4ns / call

Turns out that without any locals, the UnrealScript virtual machine needs to allocate no stack frame
at all, so it's reasonably cheap. Once we have any local variables, we need to allocate space for
the stack frame, which makes this much more expensive -- mostly regardless of the number and size of locals.

## Arguments

Initializing locals is comparatively cheap, since the default value for all property data is represented
as the all-zeros bit pattern and the stack frame just needs to be zeroed. Arguments, on the other hand,
need to be copied over, which is more costly, especially since some arguments require an unbounded
amount of memory to be copied:

```java
final function int FindMax(array<int> arr) {
    // ...
}
```

For this function, the entire array data needs to be copied too, since `FindMax` requested a copy of the full array.
For a 100-element array, this function call takes 128.1ns -- and will take longer the longer the array is.

We can improve this by using the `out` parameter mode: `out` means that we reference the original array
storage location without copying all data:

```java
final function int FindMax(out array<int> arr) {
    // ...
}
```

Again, for a 100-element array, this takes 44.6ns, but this will be independent of the array size.

This has the small disadvantage that our function could now modify the array and have it affect the calling code.
We can mark this parameter as `const out` to take away the mutability. `const out` is always meant to be a
performance optimization, since the `const` takes away all the functionality added by `out`.

{{< interjection kind="advice" >}}
`out` properties have a higher overhead on access -- don't indiscriminately mark every argument as `out`.
Arrays and structs usually make sense to pass by `out`.

958 functions in the base game make use of `const out`.
{{< /interjection >}}

### Out Parameter Soundness

One thing you might have come across with `out` parameters is that dynamic array elements can't be out parameters. Consider
the following code snippet:

```java
var array<int> TheArray;

function Ok() {
	self.TheArray.AddItem(1);
	// ❌ Error, Call to 'Evil', parameter 1: Not allowed to pass a dynamic array element as the value for an out parameter
	self.Evil(TheArray[0]);
}

function Evil(out int SomeInt) {
	self.TheArray.AddItem(3);
	`log(SomeInt); // ⚡
}
```

If we remember anything from last week's blog post, it's that arrays store their elements on a separate allocation.
By adding an element while holding a pointer to another element, the array would re-allocated and we could access freed memory
in the line commented with ⚡:

![use-after-free visualization](/img/dispatch/realloc-out.png)

{{< interjection kind="info" >}}
Any safe language must reject this; C# supports `out`/`ref` parameters too and rejects this. Both
UnrealScript and C# never allow dynamic array elements as `out`/`ref` parameters.

Rust is a safe language with a sophisticated borrow checker that would reject this particular code but doesn't disallow
dynamic array elements as references when it can prove that the array can't be modified in the function.

In unsafe languages like C and C++, retaining access to de-allocated memory cannot be prevented by the compiler and actual access
causes *use-after-free* errors, generally a security- and safety-relevant class of bugs.
{{< /interjection >}}

## Assorted Modifiers

### Static

A `static` function behaves as if it doesn't have an associated instance. Access to `self` is disallowed, and
the function can be called without having an instance. Yet, there is an owning object (the Class Default Object/CDO),
and dispatch is still virtual (since you could explicitly be calling the function on a sub-class that doesn't override
the function *yet* but does at some later point).

### Singular

Whenever a `singular` function is called, the VM sets a "we're in a singular function" flag and clears it when that function
returns. When the flag is set, calls to singular functions are **skipped**.

{{< interjection kind="advice" >}}
This is used in the base game to prevent runaway recursion from physics events. Please don't use it in any algorithms; it's global
state and an awful hack.<p />
{{< /interjection >}}

### Simulated

The `simulated` modifier is only relevant for [Replication](https://docs.unrealengine.com/udk/Three/FunctionReplication.html#Function%20replication%20and%20simulation),
the Unreal Engine 3 solution to networking and multiplayer. I don't think anyone in the XCOM 2 community understands this system well enough to
explain what `simulated` does. In XCOM 2, we mark all UI functions as `simulated` as a sort of cargo cult.

## Alternatively

... don't call any functions at all. It would be great if the UnrealScript compiler supported merging small private functions into
calling functions (called [Inlining](https://en.wikipedia.org/wiki/Inline_expansion)), but it doesn't. If you have some code
that gets slowed down significantly by leaf function calls, consider manually inlining the function body.

{{< interjection kind="info" >}}
This is something I experimented with in an [UnrealScript implementation](https://github.com/robojumper/X2WOTCCommunityHighlander/commit/4a86d70b7d320dded4e7971f9a29b28b9cbc3b65#diff-cd680b84d639d6464dca8ca8694f10a1201692892639d1191fcf04eb23de9025R510-R545) of QuickSort.
Calling the comparison function/delegate (which necessarily has arguments and a hence a stack frame) can be unreasonably expensive.<p />
{{< /interjection >}}

## Closing words

I believe that at this point, I have covered the topics I set out to cover when I started this blog post series. Expect future entries
to be published sporadically at best and to cover smaller bits and interesting facts about UnrealScript instead of grand topics.

Thanks for reading!
