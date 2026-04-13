using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using core;

public class CardDBImporter
{
    [MenuItem("Tools/Import Full Card CSV")]
    public static void Import()
    {
        string path = EditorUtility.OpenFilePanel("CSV 선택", "", "csv");
        if (string.IsNullOrEmpty(path)) return;

        var lines = File.ReadAllLines(path);

        var db = ScriptableObject.CreateInstance<CardUnitDB>();
        var list = new List<CardDefinition>();

        for (int i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i])) continue;

            var row = SplitCSV(lines[i]);

            try
            {
                var def = new CardDefinition
                {
                    cardID = ParseHex(row[0]),
                    name = row[1],
                    world = ParseHex(row[2]),
                    role = ParseRole(int.Parse(row[3])),

                    attack = int.Parse(row[4]),
                    life = int.Parse(row[5]),

                    textCondition = ParseCondition(int.Parse(row[6])),
                    textName = row[7],
                    text = row[8],

                    effectName = row[9],
                    effect = row[10]
                };

                list.Add(def);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"라인 {i} 파싱 실패: {e.Message}");
            }
        }

        db.SetData(list);

        string assetPath = "Assets/11 Scriptable Object/CardUnitDB.asset";
        AssetDatabase.CreateAsset(db, assetPath);
        AssetDatabase.SaveAssets();

        Debug.Log($"DB 생성 완료: {assetPath}");
    }

    // CSV 안전 분리 (콤마 포함 문자열 대응)
    private static string[] SplitCSV(string line)
    {
        var result = new List<string>();
        bool inQuotes = false;
        string current = "";

        foreach (char c in line)
        {
            if (c == '"') inQuotes = !inQuotes;
            else if (c == ',' && !inQuotes)
            {
                result.Add(current);
                current = "";
            }
            else current += c;
        }

        result.Add(current);
        return result.ToArray();
    }

    private static int ParseHex(string hex)
    {
        hex = hex.Replace("0x", "").Trim();
        return System.Convert.ToInt32(hex, 16);
    }

    private static string ParseRole(int role)
    {
        switch (role)
        {
            case 0: return "군주";
            case 1: return "비숍";
            case 2: return "나이트";
            case 3: return "룩";
            case 4: return "폰";
            default:
                Debug.LogError($"알 수 없는 Role: {role}");
                return "?";
        }
    }

    private static string ParseCondition(int condition)
    {
        switch (condition)
        {
            case 0: return "상시";
            case 1: return "턴 시작";
            case 2: return "턴 종료";
            case 3: return "파괴 시";
            case 4: return "기본 이동 시";
            default:
                Debug.LogError($"알 수 없는 Condition: {condition}");
                return "알 수 없음";
        }
    }
}