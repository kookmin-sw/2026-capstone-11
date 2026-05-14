using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using core.data;
using Unity.VisualScripting;

public class BuffDBImporter
{
    [MenuItem("Tools/Import Buff CSV")]
    public static void Import()
    {
        var buffList = new List<BuffDefinition>();

        string path = EditorUtility.OpenFilePanel($"CSV 선택", "", "csv");

        if (string.IsNullOrEmpty(path)) return;

        var lines = File.ReadAllLines(path);

        for (int i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i])) continue;

            var row = SplitCSV(lines[i]);

            try
            {
                buffList.Add(new BuffDefinition
                {
                    id = row[0],
                    name = row[1],
                    description = row[2],
                    useAmount = ParseHasAmount(row[2])
                });
            }
            catch (System.Exception e)
            {
                Debug.LogError($"라인 {i} 파싱 실패: {e.Message}");
            }
        }

        var db = ScriptableObject.CreateInstance<BuffDB>();

        db.SetData(buffList);

        string assetPath = "Assets/05 Scriptable Object/BuffDB.asset";
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

    private static bool ParseHasAmount(string desc) => desc.Contains("{0}");
}