using core.data;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class SelectedLeaderDisplay : MonoBehaviour
{
    [SerializeField] private SpriteRenderer portrait;

    public void Bind(Sprite sprite)
    {
        portrait.sprite = sprite;
    }
}