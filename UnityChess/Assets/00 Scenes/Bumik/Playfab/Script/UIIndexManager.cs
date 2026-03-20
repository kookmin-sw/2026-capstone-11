using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class UIIndexManager : MonoBehaviour
{
    [System.Serializable]
    struct Button_UIRegister
    {
        public Button button;
        public GameObject UIPanel;
    }

    [SerializeField] private List<Button_UIRegister> _button_UI_list;

    void Awake()
    {
        if (_button_UI_list == null) _button_UI_list = new();
        HideAll();

        foreach (var elem in _button_UI_list)
        {
            var button = elem.button;
            var UIPanel = elem.UIPanel;

            button.onClick.AddListener(
                () =>
                {
                    HideAll();
                    UIPanel.SetActive(true);
                }
            );
        }
    }

    private void HideAll()
    {
        foreach (var elem in _button_UI_list)
            elem.UIPanel.SetActive(false);
        
    }
}
