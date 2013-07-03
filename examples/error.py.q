
Error galore
============

__Undefined: {abcd}

* x = 10 {x = 10}
* x / 3 == {x / 3}
* x / 2 == {x / 2}
* x / 1 == {x / 1}
* x / 0 == {x / 0}

This definition will fail:

python %
  {
    engine["/ x"] = lambda: "wrong signature"
  }

{
  engine["/ x"] = lambda: "wrong signature"
}

I don't know what I am /doing here.


