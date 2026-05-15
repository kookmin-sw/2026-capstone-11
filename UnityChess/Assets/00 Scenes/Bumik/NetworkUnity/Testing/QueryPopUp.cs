using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;
using TMPro;
using Unity.VisualScripting.AssemblyQualifiedNameParser;
using UnityEngine;
using UnityEngine.UI;

public class QueryPopUp : MonoBehaviour
{
    [SerializeField] private Image popUpScreen;
    [SerializeField] private TMP_Text ActinoListText;
    [SerializeField] private TMP_InputField ActionIndexInput;
    [SerializeField] private Button ResponseButton;

    private int _current_query = 0;

    private List<(string uid, string effectId)> _actionList = new();

    public void Init()
    {
        popUpScreen.enabled = false;

        ResponseButton.onClick.AddListener(Response);
    }


    public void PopScreen(int queryNum, byte[] data)
    {
        popUpScreen.enabled = true;
        _current_query = queryNum;

        // ActionList 파싱.
        string msg = Encoding.UTF8.GetString(data);
        _actionList = ParseActions(msg);

        ActinoListText.text = Convert.ToString(ActionsToString(_actionList));
    }

    public void Response()
    {
        if (int.TryParse(ActionIndexInput.text, out int idx))
        {
            string uid = GetUidByIndex(_actionList, idx);
            NetworkManagerUnity.Instance.Session.Answer(_current_query, Encoding.UTF8.GetBytes(uid));
            popUpScreen.enabled = false;
        }
    }

    public List<(string uid, string content)> ParseActions(string json)
    {
        var root = JObject.Parse(json);

        return root["Actions"]?
            .Children<JObject>()
            .Select(action =>
            {
                string uid = action["Uid"]?.ToString() ?? string.Empty;

                var parts = new List<string>();

                foreach (var prop in action.Properties())
                {
                    if (prop.Name == "Uid")
                        continue;

                    if (prop.Value is JObject obj)
                    {
                        foreach (var subProp in obj.Properties())
                        {
                            parts.Add(subProp.Value?.ToString() ?? string.Empty);
                        }
                    }
                    else
                    {
                        parts.Add(prop.Value?.ToString() ?? string.Empty);
                    }
                }

                string content = string.Join(" | ", parts);

                return (uid, content);
            })
            .ToList()
            ?? new List<(string uid, string content)>();
    }

    public string ActionsToString(List<(string uid, string effectId)> actions)
    {
        if (actions == null || actions.Count == 0)
            return string.Empty;

        return string.Join("\n", actions.Select(x => $"({x.uid}, {x.effectId})"));
    }

    public string GetUidByIndex(List<(string uid, string effectId)> actions, int idx)
    {
        if (actions == null || idx < 0 || idx >= actions.Count)
            return string.Empty;

        return actions[idx].uid;
    }


}
