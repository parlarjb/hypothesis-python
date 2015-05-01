================
Stateful testing
================

Hypothesis offers support for a stateful style of test, where instead of
trying to produce a single data value that causes an error it tries to produce
a sequence of actions which cause an error. It can essentially be thought of
as a tool for using Hypothesis to generate *programs* instead of mere data.

Right now the stateful testing is a bit new and experimental. This should be
considered semi-public API: It may break between minor versions but won't
break between patch releases.

This also means that it's a somewhat less polished product than the rest of
Hypothesis. It should generally work fine, but it has some rough edges that
still need to be filed off.

Additionally the stateful testing API feels a bit alien to the way Hypothesis
otherwise works, and should perhaps be considered its own thing and merely
built on top of Hypothesis. The two APIs may converge over time as I better
figure out how this should work.

Still, stateful testing is an extremely powerful approach and even with these
limitations it's a great way to test your code. Giving it a try anyway and
report back is the #1 way for it to improve.

There are two levels of API: The low level but more flexible API and the
rule based API which is both easier to use and also produces a much better
display of data due to its greater structure. We'll start with the more
structured one.

-------------------------
Rule based state machines
-------------------------

Rule based state machines are the ones you're most likely to want to use.

A rule based state machine is a collection of functions (possibly with side
effects) which may depend on both values that Hypothesis can generate and
also on values that have resulted from previous function calls.

You define a rule based state machine as follows:

.. code:: python

  import unittest
  from collections import namedtuple

  from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule


  Leaf = namedtuple('Leaf', ('label',))
  Split = namedtuple('Split', ('left', 'right'))


  class BalancedTrees(RuleBasedStateMachine):
      trees = Bundle('BinaryTree')

      @rule(target=trees, x=int)
      def leaf(self, x):
          return Leaf(x)

      @rule(target=trees, left=trees, right=trees)
      def split(self, left, right):
          return Split(left, right)

      @rule(tree=trees)
      def check_balanced(self, tree):
          if isinstance(tree, Leaf):
              return
          else:
              assert abs(self.size(tree.left) - self.size(tree.right)) <= 1
              self.check_balanced(tree.left)
              self.check_balanced(tree.right)

      def size(self, tree):
          if isinstance(tree, Leaf):
              return 1
          else:
              return 1 + self.size(tree.left) + self.size(tree.right)

In this we declare a Bundle, which is a named collection of previously generated
values. We define two rules which put data onto this bundle - one which just
generates leaves with integer labels, the other of which takes two previously
generated values and returns a new one.

We can then integrate this into our test suite by getting a unittest TestCase
from it:

.. code:: python

  TestTrees = BalancedTrees.TestCase

  if __name__ == '__main__':
      unittest.main()

(these will also be picked up by py.test if you prefer to use that). Running
this we get:

.. code:: bash

  Step #1: v1 = leaf(x=0)
  Step #2: v2 = split(left=v1, right=v1)
  Step #3: v3 = split(left=v2, right=v1)
  Step #4: check_balanced(tree=v3)
  F
  ======================================================================
  FAIL: runTest (hypothesis.stateful.BalancedTrees.TestCase)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
  (...)
  assert abs(self.size(tree.left) - self.size(tree.right)) <= 1
  AssertionError

Note how it's printed out a very short program that will demonstrate the
problem.

...the problem of course being that we've not actually written any code to
balance this tree at *all*, so of course it's not balanced.

So lets balance some trees.


.. code:: python

  class BalancedTrees(RuleBasedStateMachine):
      trees = Bundle('BinaryTree')
      balanced_trees = Bundle('balanced BinaryTree')

      @rule(target=trees, x=int)
      def leaf(self, x):
          return Leaf(x)

      @rule(target=trees, left=trees, right=trees)
      def split(self, left, right):
          return Split(left, right)

      @rule(tree=balanced_trees)
      def check_balanced(self, tree):
          if isinstance(tree, Leaf):
              return
          else:
              assert abs(self.size(tree.left) - self.size(tree.right)) <= 1, \
                  repr(tree)
              self.check_balanced(tree.left)
              self.check_balanced(tree.right)


    @rule(target=balanced_trees, tree=trees)
    def balance_tree(self, tree):
        return self.split_leaves(self.flatten(tree))

      def size(self, tree):
          if isinstance(tree, Leaf):
              return 1
          else:
              return self.size(tree.left) + self.size(tree.right)

      def flatten(self, tree):
          if isinstance(tree, Leaf):
              return (tree.label,)
          else:
              return self.flatten(tree.left) + self.flatten(tree.right)

      def split_leaves(self, leaves):
          assert leaves
          if len(leaves) == 1:
              return Leaf(leaves[0])
          else:
              mid = len(leaves) // 2
              return Split(
                  self.split_leaves(leaves[:mid]),
                  self.split_leaves(leaves[mid:]),
              )

We've now written a really noddy tree balancing implementation. 

If you run this it will sit their silently for a while (you can turn on
verbose output to get slightly more information about what's happening) and
then run, telling you your test has passed! Our balancing algorithm worked.

Now lets break it to make sure the test is still valid:

Changing the split to mid = max(len(leaves) // 3, 1) this should no longer
balance, which gives us the following counter-example:

.. code:: python

  v1 = leaf(x=0)
  v2 = split(left=v1, right=v1)
  v3 = balance_tree(tree=v1)
  v4 = split(left=v2, right=v2)
  v5 = balance_tree(tree=v4)
  check_balanced(tree=v5)

Note that the example could be shrunk further by deleting v3. Due to some
technical limitations, Hypothesis was unable to find that particular shrink.
In general it's rare for examples produced to be long, but they might not
always be minimal right now.

You can control the deailed behaviour with a Settings object on the TestCase
(this is a normal hypothesis Settings object using the defaults at the time
the TestCase class was first referenced). For example if you wanted to run
fewer examples with larger programs you could change the settings to:

.. code:: python

  TestTrees.settings.max_examples = 100
  TestTrees.settings.stateful_step_count = 100

Which doubles the number of steps each program runs and halves the number of
runs relative to the example.

----------------------
Generic state machines
----------------------

The class GenericStateMachine is the underlying machinery of stateful testing
in Hypothesis. In execution it looks much like the RuleBasedStateMachine but 
it allows the set of steps available to depend in essentially arbitrary
ways on what has happened so far. For example, if you wanted to
use Hypothesis to test a game, it could choose each step in the machine based
on the game to date and the set of actions the game program is telling it it
has available.

It essentially executes the following loop:

.. code:: python

  machine = MyStateMachine()
  try:
    for _ in range(n_steps):
      step = machine.steps().example()
      machine.execute_step(step)
  finally:
    machine.teardown()

Where steps() and execute_step() are methods you must implement, and teardown
is a method you can implement if you need to clean something up at the end. steps 
returns a strategy, which is allowed to depend arbitrarily on the current
state of the test execution (though ideally should be robust against minor
changes in the state. It's not required, but the less your steps() change the
higher the quality of examples you'll get). 

If any of execute_step or teardown produces an error, Hypothesis will try to
find a minimal sequence of values steps such that the following throws an
exception:

.. code:: python

  try:
    machine = MyStateMachine()
    for step in steps:
      machine.execute_step(step)
  finally:
    machine.teardown()

and such that at every point, the step executed is one that could plausible
have come from a call to steps() in the current state.

Here's an example of using stateful testing to test a broken implementation
of a set in terms of a list (note that you could easily do something close to
this example with the rule based testing instead, and probably should. This
is mostly for illustration purposes):

.. code:: python

    import unittest

    from hypothesis.stateful import GenericStateMachine
    from hypothesis import strategy
    from hypothesis.specifiers import sampled_from, just


    class BrokenSet(GenericStateMachine):
        def __init__(self):
            self.data = []

        def steps(self):
            add_strategy = strategy((just("add"), int))
            if not self.data:
                return add_strategy
            else:
                return (
                    add_strategy |
                    strategy((just("delete"), sampled_from(self.data)))
                )

        def execute_step(self, step):
            action, value = step
            if action == 'delete':
                try:
                    self.data.remove(value)
                except ValueError:
                    pass
                assert value not in self.data
            else:
                assert action == 'add'
                self.data.append(value)
                assert value in self.data


    TestSet = BrokenSet.TestCase

    if __name__ == '__main__':
        unittest.main()


Note that the strategy changes each time based on the data that's currently
in the state machine.

Running this gives us the following:

.. code:: bash

  Step #1: ('add', 0)
  Step #2: ('add', 0)
  Step #3: ('delete', 0)
  F
  ======================================================================
  FAIL: runTest (hypothesis.stateful.BrokenSet.TestCase)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
  (...)
      assert value not in self.data
  AssertionError

So it adds two elements, then deletes one, and throws an assertion when it
finds out that this only deleted one of the copies of the element.