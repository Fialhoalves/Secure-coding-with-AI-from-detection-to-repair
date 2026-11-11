import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE / "src"))

CODE_C = """#include <stdio.h>
#include <string.h>
void greet(const char *name) {
    char buf[16];
    strcpy(buf, name);
    printf("Hello %s\\n", buf);
}
int main(int argc, char **argv) {
    if (argc > 1) greet(argv[1]);
    return 0;
}
"""
CODE_CPP = CODE_C.replace("greet", "hello").replace("strcpy(buf, name);", "strcpy(buf, name); // copy")
CODE_CS = "class A {\n    static void Main(string[] args) {\n        System.Console.WriteLine(args[0]);\n    }\n}\n"


@pytest.fixture
def cfg(tmp_path):
    from config import load_config
    return load_config(PIPELINE / "config.yaml", root=PIPELINE.parent, work_dir=tmp_path)


@pytest.fixture
def items():
    from agents import CodeItem
    return [CodeItem("v8:File_01", "v8", 1, "C", ".c", CODE_C, "positive"),
            CodeItem("v8:File_02", "v8", 2, "C++", ".cpp", CODE_CPP, "negative"),
            CodeItem("v10:File_03", "v10", 3, "C#", ".cs", CODE_CS, "negative")]
