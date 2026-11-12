# Hash dos prompts congelados

SHA-256 do conteúdo de cada arquivo desta pasta. O hash faz parte da chave do cache (`pipeline/src/prompts.py` usa os 12 primeiros caracteres), então alterar um prompt gera chamadas novas.

| Arquivo | SHA-256 |
|---|---|
| `a1_v1.md` | `304cd04c28b3cee22932cebd35e53b6a79e9b02c32e46bfabc726ba6ed82beda` |
| `a1_v2.md` | `3570116ae7f61bee55e299107eb881b0dcc1a182484466219036b62011b982fb` |
| `a2_v1.md` | `9cf8220b6c4c33fd5818b293030ccfcec22bbe7d793cb34a2af3fefa10acd67b` |
| `a3_v1.md` | `f9384f9cc0f5e40d6ab890f379e0a864fd231a46c849ca2eadd7fa01f184e189` |
| `a3b_v1.md` | `77d3f2710f6ea58dd55d1f048ff3990eeed4a59afaa189539b708c2d83ac8653` |
| `b0_paper.md` | `78c987ed8d98a2c40894df183b39eb1de893a02319404095a1bbbcd12e27e92c` |
| `b0_extract_v1.md` | `f67fa0fbc80d19e16d169a797c56b7d870878842509361d5641007e59136014c` |

`a1_v1` é o prompt usado no piloto e foi substituído por `a1_v2` antes da execução principal. Os demais foram os usados na execução principal.
