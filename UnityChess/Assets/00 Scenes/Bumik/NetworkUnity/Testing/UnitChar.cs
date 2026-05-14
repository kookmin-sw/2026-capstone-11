using UnityEngine;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class UnitChar : MonoBehaviour
{
    [Header("UI")]
    [SerializeField] private Image background;
    [SerializeField] private TMP_Text uidText;
    [SerializeField] private TMP_Text idText;
    [SerializeField] private TMP_Text hpText;
    [SerializeField] private TMP_Text atkText;

    public void SetEmpty()
    {
        if (uidText != null) uidText.text = "";
        if (idText != null) idText.text = "";
        if (hpText != null) hpText.text = "";
        if (atkText != null) atkText.text = "";

        if (background != null)
        {
            var c = background.color;
            c.a = 0.15f;
            background.color = c;
        }
    }

    public void SetData(string uid, string id, int hp, int atk)
    {
        if (uidText != null) uidText.text = $"Uid: {uid}";
        if (idText != null) idText.text = $"Id: {id}";
        if (hpText != null) hpText.text = $"Hp: {hp}";
        if (atkText != null) atkText.text = $"Atk: {atk}";

        if (background != null)
        {
            var c = background.color;
            c.a = 1f;
            background.color = c;
        }
    }
}